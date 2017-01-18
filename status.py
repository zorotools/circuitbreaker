import argparse
import redis
import logging
import sys
from tabulate import tabulate
from circuitbreaker.circuitbreaker import Endpoint


def get_rate(numerator, denominator):
    if denominator:
        rate = str(round(numerator / float(len(denominator)) * 100, 2)) + "%"
    else:
        rate = "N/A"
    return rate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check the current status of an endpoint')
    parser.add_argument('-H', '--host', dest='host', metavar=('hostname'), default='localhost',
                        help='Specify which Redis host to connect to. Defaults to "localhost"')
    parser.add_argument('-p', '--port', dest='port', metavar=('port'), default=6379,
                        help='Specify the port to use for connecting to the Redis host. Defaults to 6379')
    parser.add_argument('-P', '--password', dest='password', metavar=('password'), default=None,
                        help='Specify a password to use when connecting to the Redis host. Defaults to None')
    parser.add_argument('-e', '--endpoint', dest='endpoint', metavar=('endpoint'),
                        help='The enpoint name to check')
    args = parser.parse_args()

    redis_connection = redis.StrictRedis(host=args.host, port=args.port, password=args.password, db=0)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    endpoint = Endpoint(args.endpoint, redis_connection, logger)
    is_healthy = True if endpoint.is_healthy() else False

    status = [
        ('Health', "healthy" if is_healthy else "unhealthy")
    ]

    if is_healthy:
        history = endpoint.redis.lrange(endpoint.name + ':history', 0, -1)
        successes = history.count(b'1')
        status.extend([
            ('History Cases', len(history)),
            ('History Successes', successes),
            ('History Success Rate', get_rate(successes, history)),
            ('Failure Threshold', str(endpoint.settings['failure_threshold'] * 100) + "%")
        ])
    else:
        test_count = endpoint.redis.get(endpoint.name + ':test_count')
        test_history = endpoint.redis.lrange(endpoint.name + ':test_history', 0, -1)
        successes = test_history.count(b'1')
        status.extend([
            ('Test Count', int(test_count)),
            ('Test History Cases', len(test_history)),
            ('Test History Successes', successes),
            ('Test History Success Rate', get_rate(successes, test_history)),
            ('Recovery Threshold', str(endpoint.settings['recovery_threshold'] * 100) + "%")
        ])

    print(tabulate(status, tablefmt="fancy_grid"))
