import redis
import os
import logging


REDIS_CONNECTOR = None
LOGGER = None


# the redis adapter is annoying and returns everything as an ascii string (Python 2)
# or as bytes (Python 3), this function exists to parse the data to its intended format
def parse_num(data):
    try:
        return int(data)
    except ValueError as e:
        return float(data)


def set_up_redis(redis_config=None):
    global REDIS_CONNECTOR
    if not REDIS_CONNECTOR:
        # if no redis config was passed, use environment variables
        if not redis_config:
            redis_host = os.environ.get('CB_REDIS_HOSTNAME', 'localhost')
            redis_port = int(os.environ.get('CB_REDIS_PORT', 6379))
            redis_pass = os.environ.get('CB_REDIS_PASS', None)
            redis_timeout = int(os.environ.get('CB_REDIS_TIMEOUT', 3))
        # if the config is a dictionary, parse it for connection data
        elif type(redis_config) is dict:
            redis_host = redis_config.get('host', 'localhost')
            redis_port = redis_config.get('port', 6379)
            redis_pass = redis_config.get('pass', None)
            redis_timeout = redis_config.get('timeout', 3)
        # if none of the above, assume the config is a redis connection object and use it directly
        else:
            REDIS_CONNECTOR = redis_config
            return
        REDIS_CONNECTOR = redis.StrictRedis(host=redis_host, port=redis_port, db=0, password=redis_pass, socket_timeout=redis_timeout)


def set_up_logger(config=None):
    global LOGGER
    # if an existing logger was passed in, use it
    if config:
        LOGGER = config
    # if a global logger doesn't already exist, set up a dummy logger
    elif not LOGGER:
        logger = logging.getLogger(__name__)
        LOGGER = logger


class CircuitBreaker(object):
    def __init__(self, endpoints, redis_config=None, logger_config=None):
        self._endpoints = endpoints[:]
        self._endpoint = None
        self._complete = False
        self._prefix = ''
        set_up_redis(redis_config)
        set_up_logger(logger_config)
        # check the connection to the Redis server, and consider all endpoints invalid if we can't connect
        global REDIS_CONNECTOR
        global LOGGER
        try:
            REDIS_CONNECTOR.ping()
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            REDIS_CONNECTOR = None
            self._endpoints = []
            LOGGER.error(str(e))

    def get_next_endpoint(self):
        while self._endpoints or self._endpoint:
            # if there is currently an endpoint defined for this instance, don't move on to the next endpoint
            if self._endpoint:
                if self._endpoint.name.startswith(self._prefix):
                    yield self._endpoint.name[len(self._prefix):]
                else:
                    yield self._endpoint.name
            else:
                endpoint = self._endpoints.pop(0)
                current_endpoint = Endpoint(self._prefix + endpoint)
                if current_endpoint.is_active():
                    self._endpoint = current_endpoint
                    if self._endpoint.name.startswith(self._prefix):
                        yield self._endpoint.name[len(self._prefix):]
                    else:
                        yield self._endpoint.name

    def succeed(self):
        if self._endpoint and not self._complete:
            self._endpoint.mark_success()
            self._complete = True

    def fail(self):
        if self._endpoint and not self._complete:
            self._endpoint.mark_failure()
            self._endpoint = None

    def did_succeed(self):
        return self._complete

    def set_prefix(self, prefix):
        self._prefix = prefix


class Endpoint(object):
    def __init__(self, endpoint_name, redis_connector=None, logger=None):
        if redis_connector:
            self.redis = redis_connector
        else:
            global REDIS_CONNECTOR
            self.redis = REDIS_CONNECTOR
        if logger:
            self.logger = logger
        else:
            global LOGGER
            self.logger = LOGGER
        self.name = endpoint_name
        if not self.redis.exists(self.name):
            settings = {
                "failure_threshold": .95,
                "recovery_threshold": .95,
                "min_history_size": 100,
                "max_history_size": 1000,
                "test_history_size": 100,
                "test_group_size": 5,
                "test_skip_size": 1000
            }
            pipe = self.redis.pipeline()
            pipe.set(self.name, "healthy")
            pipe.hmset(self.name + ':settings', settings)
            pipe.set(self.name + ':test_count', 0)
            pipe.execute()
        s = self.redis.hgetall(self.name + ':settings')
        self.settings = {}
        for setting, value in s.items():
            self.settings[setting.decode('utf-8')] = parse_num(value)
        self.status = self._get_status()

    def is_healthy(self):
        return self.status == 'healthy'

    def is_active(self):
        return self.status in ('healthy', 'testing')

    def mark_success(self):
        self._record_attempt(1)

    def mark_failure(self):
        self._record_attempt(0)

    def update_settings(self, **kwargs):
        self.redis.hmset(self.name + ':settings', kwargs)

    def _record_attempt(self, success):
        # Push the latest attempt to whichever history list is appropriate, then trim that list down to its max size
        if self.status == 'healthy':
            pipe = self.redis.pipeline()
            pipe.lpush(self.name + ':history', success)
            pipe.ltrim(self.name + ':history', 0, self.settings['max_history_size'] - 1)
            pipe.execute()
            if self._is_failed():
                self._fail()
        elif self.status == 'testing':
            pipe = self.redis.pipeline()
            pipe.lpush(self.name + ':test_history', success)
            pipe.ltrim(self.name + ':test_history', 0, self.settings['test_history_size'] - 1)
            pipe.execute()
            if self._is_recovered():
                self._recover()

    def _get_status(self):
        status = self.redis.get(self.name).decode('utf-8')
        if status == 'unhealthy':
            count = int(self.redis.incr(self.name + ':test_count'))
            mod = count % (self.settings['test_skip_size'] + self.settings['test_group_size'])
            if mod >= self.settings['test_skip_size']:
                return 'testing'
            else:
                return 'unhealthy'
        else:
            return 'healthy'

    def _is_recovered(self):
        tests = self.redis.lrange(self.name + ':test_history', 0, -1)
        if len(tests) >= self.settings['test_history_size']:
            successes = tests.count(b'1')
            if successes / float(len(tests)) >= self.settings['recovery_threshold']:
                return True
        return False

    def _recover(self):
        status = self.redis.getset(self.name, 'healthy')
        if status != 'healthy':
            self.logger.info('{0} has recovered. It is being placed in a "healthy" state.'.format(self.name))
            self._reset()

    def _is_failed(self):
        history = self.redis.lrange(self.name + ':history', 0, -1)
        if len(history) >= self.settings['min_history_size']:
            successes = history.count(b'1')
            if successes / float(len(history)) < self.settings['failure_threshold']:
                return True
        return False

    def _fail(self):
        status = self.redis.getset(self.name, 'unhealthy')
        if status != 'unhealthy':
            self.logger.info('{0} has failed. It is being placed in an "unhealthy" state.'.format(self.name))
            self._reset()

    def _reset(self):
        pipe = self.redis.pipeline()
        pipe.set(self.name + ':test_count', 0)
        pipe.delete(self.name + ':history')
        pipe.delete(self.name + ':test_history')
        pipe.execute()
