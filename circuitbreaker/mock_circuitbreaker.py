import mockredis


class MockCircuitBreaker(object):
    def __init__(self, endpoints, redis_config=None, logger_config=None):
        self.redis_config = redis_config
        self.redis = self.set_up_redis()
        self.logger_config = logger_config
        self._endpoints = endpoints
        self._endpoint = None
        self._complete = True

    def get_endpoints_name(self):
        names = []
        for endpoint in self._endpoints:
            for key, value in endpoint.items():
                names.append(key)
        return names

    def get_next_endpoint(self):
        with self._endpoints or self._endpoint:
            if self._endpoint and isinstance(self._endpoint, dict):
                endpoint_name = self._endpoint.keys()
                if self._endpoint.get(endpoint_name[0]) == 'healthy':
                    yield endpoint_name[0]
            else:
                endpoint_name = self.get_endpoints_name()
                for index, endpoint in enumerate(self._endpoints):
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