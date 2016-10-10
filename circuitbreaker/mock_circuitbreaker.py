import mockredis


class CircuitBreaker(object):
    def __init__(self, endpoints, redis_config=None, logger_config=None):
        self.redis_config = redis_config
        self.redis = self.set_up_redis()
        self.logger_config = logger_config
        self._endpoints = endpoints
        self._endpoint = None
        self._complete = True

    def get_next_endpoint(self):
        with self._endpoints or self._endpoint:
            if self._endpoint and isinstance(self._endpoint, dict):
                endpoint_name = self._endpoint.keys()
                if self._endpoint.get(endpoint_name[0]) == 'healthy':
                    yield endpoint_name[0]
            else:
                for index, endpoint in enumerate(self._endpoints):
                    endpoint_name = list(endpoint.keys())
                    if endpoint.get(endpoint_name[index]) == 'healthy':
                        yield endpoint_name[index]

    @staticmethod
    def set_up_redis():
        return mockredis.MockRedis()

    def succeed(self):
        pass

    def fail(self):
        pass

    def did_succeed(self):
        return self._complete

    def set_prefix(self, prefix):
        pass