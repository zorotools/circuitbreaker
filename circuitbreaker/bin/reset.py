import argparse
import redis
import logging
import sys
from circuitbreaker.circuitbreaker import Endpoint


def main():
    parser = argparse.ArgumentParser(description='Resets an endpoint\'s history and marks it as "healthy" or "unhealthy"')
    parser.add_argument('-H', '--host', dest='host', metavar=('hostname'), required=True,
                        help='Specify which Redis host to connect to')
    parser.add_argument('-p', '--port', dest='port', metavar=('port'), default=6379,
                        help='Specify the port to use for connecting to the Redis host. Defaults to 6379')
    parser.add_argument('-P', '--password', dest='password', metavar=('password'), default=None,
                        help='Specify a password to use when connecting to the Redis host. Defaults to None')
    parser.add_argument('-e', '--endpoint', dest='endpoint', metavar=('endpoint'), required=True,
                        help='The enpoint name to be reset')
    parser.add_argument('-u', '--unhealthy', action='store_true',
                        help='Mark the endpoint as "unhealthy". It will be marked as "healthy" otherwise.')
    args = parser.parse_args()

    redis_connection = redis.StrictRedis(host=args.host, port=args.port, password=args.password, db=0)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    endpoint = Endpoint(args.endpoint, redis_connection, logger)
    if args.unhealthy:
        endpoint._fail()
    else:
        endpoint._recover()


if __name__ == '__main__':
    main()