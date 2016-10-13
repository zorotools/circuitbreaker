import mockredis

UNHEALTHY_ENDPOINTS = []


class MockCircuitBreaker(object):
    def __init__(self, endpoints, redis_config=None, logger_config=None):
        self.redis_config = redis_config
        self.redis = self.set_up_redis()
        self.logger_config = logger_config
        self._endpoints = endpoints
        self._endpoint = None
        self._complete = True
        self.unhealthy_endpoints = UNHEALTHY_ENDPOINTS

    def is_active(self, endpoint):
        if not self.unhealthy_endpoints:
            return True
        return endpoint not in self.unhealthy_endpoints

    def get_next_endpoint(self):
        while self._endpoints or self._endpoint:
            if self._endpoint:
                yield self._endpoint.name
            else:
                current_endpoint = self._endpoints.pop(0)
                if self.is_active(current_endpoint):
                    yield current_endpoint

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