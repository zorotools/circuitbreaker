from setuptools import setup, find_packages

setup(
    name='zorocircuitbreaker',
    version='0.9.7',
    description='An implementation of the circuit breaker pattern',
    url='https://www.bitbucket.com/zorotools/circuit-breaker/',
    author='Zoro',
    author_email='zoroengineering@zoro.com',
    install_requires=['hiredis>=0.2.0', 'redis>=2.10.5', 'mockredis'],
    packages=['circuitbreaker']
)
