from setuptools import setup, find_packages

setup(
    name='zorocircuitbreaker',
    version='0.9.3',
    description='An implementation of the circuit breaker pattern',
    url='https://www.bitbucket.com/zorotools/circuit-breaker/',
    author='Zoro',
    author_email='zoroengineering@zoro.com',
    install_requires=['graypy>=0.2.14', 'hiredis>=0.2.0', 'redis>=2.10.5'],
    packages=['circuitbreaker']
)