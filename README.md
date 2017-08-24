# Zoro Circuit Breaker

## Purpose

This repo is intended for use in creating a circuit-breaker pattern for calls to external resources. This project is only concerned with tracking the health of various endpoints and relaying that information. The details for how to determine what constitutes a success or failure of any given endpoint is left up to the code implementing this package, as is the handling of the health data that this returns.

More details on the circuit breaker pattern here: <https://en.wikipedia.org/wiki/Circuit_breaker_design_pattern>

## Usage

1. Create a new instance of the `CircuitBreaker` class, passing in one to three arguments:
    1. A list of endpoint names.
    1. Connection details for the Redis server (optional).
    1. A logger object (optional).
1. (Optional) Set an environment-specific prefix to prevent health data from QA environments mixing with production on a shared Redis instance.
1. Call the method `get_next_endpoint` on the newly created instance to begin iterating over healthy endpoints.
    * If use of the endpoint succeeds, call the `succeed` method on the `CircuitBreaker` instance and cease iterating over further endpoints (usually by breaking out of a loop).
    * If use of the endpoint fails, call the `fail` method and continue iterating to get the next endpoint and try it.
1. Call the method `did_succeed` to determine if one of the endpoint calls was successful, and behave appropriately.


In all, a single use of this package should look like this:

```python
from circuitbreaker import CircuitBreaker

endpoints = [
    'https://searchservice.com/primary',
    'https://searchservice.com/secondary'
]
redis_config = {
    'host': 'localhost',
    'port': 6379
}

circuit = CircuitBreaker(endpoints, redis_config)
circuit.set_prefix('qa_')
for endpoint in circuit.get_next_endpoint():
  search = do_search_request_somehow(endpoint)
  if search.success:
      circuit.succeed()
      break
  else:
      circuit.fail()
if not circuit.did_succeed():
  perform_fallback_behavior()
```

## Installation

This repository is set up to be installable as a pip package. "Releases" are denoted as tags on commits to provide versioning. To include in your project, add The following line to your `requirements.txt` file:

```bash
git+https://github.com/zorotools/circuitbreaker.git@{{version_tag_name}}
```

You can also install it directly with
```bash
pip install git+https://github.com/zorotools/circuitbreaker.git@{{version_tag_name}}
```
However, note that a `pip freeze` afterward will include only the name of the package, not its GitHub URL, which is not enough for installation from a requirements file.

Once the package has been installed, you can access the `CircuitBreaker` class by importing it from the `circuitbreaker` module:

```python
from circuitbreaker import CircuitBreaker
```

## API

### Constructor
`circuit = CircuitBreaker(endpoints, redis_config=None, logger_config=None)`

* `endpoints` expects a list of endpoint names. The endpoint names will be checked in their respective order, and the first that is found to be healthy will be used.
* `redis_config` supports several types:
  * `None`: If a value is not supplied, the circuit breaker will check system for the following environment variables and use their values to make a connection to a Redis server:
    * `CB_REDIS_HOSTNAME` should contain the hostname or IP of the Redis server
    * `CB_REDIS_PORT` should contain the port number on which the Redis server is listening
    * `CB_REDIS_PASS` should contain the password that the Redis server will use for authentication (if the Redis server does not expect a password, this environment variable can be excluded)
  * `dict`: If a dictionary is supplied, the circuit breaker will check it for the following keys, and use their values to make a connection to a Redis server:
    * `host` should contain the hostname or IP of the Redis
    * `port` should contain the port number on which the Redis server is listening
    * `pass` should contain the password that the Redis server will use for authentication (if the Redis server does not expect a password, this key can be excluded)
  * If the type of the supplied argument does not match any of the above types, it will be assumed that the supplied argument is an already-instantiated object that follows the Redis API and can be used directly as a Redis connection.
* `logger_config` expects a `logging.Logger` type object which will be used to write any log messages the circuit breaker needs to create.

### get_next_endpoint()
`for endpoint in circuit.get_next_endpoint():`

A generator which yields the name of the next healthy endpoint to attempt using. The generator will only yield the next result once `fail` has been called on the previous result. Once `succeed` has been called, the endpoint that was active at the time will be yielded for all further calls to `get_next_endpoint` on that instance. Example:

```python
>>> i = circuit.get_next_endpoint()
>>> next(i)
'endpoint_1'
>>> next(i)
'endpoint_1'
>>> circuit.fail()
>>> next(i)
'endpoint_2'
>>> circuit.succeed()
>>> next(i)
'endpoint_2'
>>> circuit.fail()
>>> next(i)
'endpoint_2'
```

### succeed()
`circuit.succeed()`

Adds a successful use of this endpoint to the history data. Once this method has been called, the `get_next_endpoint` method of the `CircuitBreaker` instance for which it was called will always return the current endpoint, and the `fail` method will not actually mark a failure. Has no return value.

### fail()
`circuit.fail()`

Adds a failed use of this endpoint to the history data. Once this has been called on a `CircuitBreaker` instance, `get_next_endpoint` can be called again. Has no return value.

### did_succeed()
`circuit.did_succeed()`

Returns a boolean. `True` if `succeed()` has already been called on the current circuit, `False` if it hasn't. This method can be used after looping over healthy endpoints to determine if one of them finished successfully or if a fallback behavior is necessary.

### set_prefix(prefix)
`circuit.set_prefix('qa_')`

Creates a prefix to use when reading/writing endpoint data to the Redis database. Since some environments (like staging and production) may share a Redis instance, adding a prefix will prevent test data from each environment from contaminating the other. The prefix will be used within the circuit breaker system to interact with the Redis DB, but will not be included in values yielded by the `get_next_endpoint` generator.

## Edge Cases

* The Redis connection is treated as a singleton. Once it has been established by the first instantiation of a `CircuitBreaker` object in any give Python process, instantiating a new `CircuitBreaker` with different Redis connection details will result in the circuit breaker ignoring the new connection details and using the existing Redis connection.

* If a `CircuitBreaker` object fails to even connect to the Redis server, it will consider all endpoints invalid and calls to `circuit.get_next_endpoint()` will always return `None`. It will also delete the Redis connection singleton, so that the next `CircuitBreaker` instance will attempt to recreate it.

* If a backup endpoint is marked as unhealthy, and the primary endpoint returns to full heath before or at the same time as the secondary endpoint, it will be very difficult the circuit breaker to return the backup endpoint to a healthy state, since it will no longer be receiving any traffic. To combat this, `cb_reset` is included in this repository. It is a command line tool that allows you to manually reset any arbitrary endpoint name to a "healthy" or "unhealthy" state. Run `cb_reset --help` from an environment where this package is installed for details on usage.

## Failure and recovery management

This package uses a Redis database to keep track of health data associated with any endpoints users decide to create. Whenever an endpoint is used, its success or failure is added to a list of historic calls to that endpoint. If the success percentage of items in that list falls below a user-defined level, that endpoint will be marked as unhealthy. If a new `CircuitBreaker` instance is created with the now-unhealthy endpoint in its list of possible endpoints, it will be skipped and the next endpoint in the list will be checked.

Once an endpoint has been marked as unhealthy, it will occasionally (at a user-defined interval) be marked as "testing", which generally means it will be treated as if it were healthy. The only difference is the successes and failures will be tracked in a separate history list. If that separate history list reaches a user-defined success percentage threshold, the endpoint will be assumed to have recovered, and will be marked as healthy.

To view the detailed heath status of an endpoint, the command line tool `cb_status` is included with this repository. Given an endpoint name, it will print a formatted table of the endpoint's current health status and request history, along with its threshold settings. Run `cb_status --help` from an environment where this package is installed for details on usage.

## Advanced configuration

All of the data stored in Redis is stored by a key based on the endpoint name (represented below as `{{endpoint_name}}`). If an environment prefix is used, it will be prepended to the base endpoint name to determine the key. The various keys used by this system are listed below, along with a detailed description of what they are and how they're used.

### {{endpoint_name}}
This key stores a simple string value of either "healthy" or "unhealthy", describing the current health state of the endpoint.

### {{endpoint_name}}:history
This key stores a list of `1`s and `0`s, representing successes and failures respectively. Successes and failures are added to this list while the endpoint is operating in "healthy" mode. The number of `1`s in this list divided by the total length of the list determines the success percentage of the endpoint. If said success percentage falls below a user defined threshold, the endpoint will be marked as "unhealthy".

### {{endpoint_name}}:test_history
This key also stores a list of `1`s and `0`s, also representing success and failures respectively. Successes and failures are added to this list while the endpoint is "unhealthy", and temporarily operating in "testing" mode. The number of `1`s in this list divided by the total length of the list determines the success percentage of the test. If said success percentage rises above a user defined threshold, the endpoint will be marked as "healthy".

### {{endpoint_name}}:test_count
This stores an integer representing the number of times the endpoint has been either skipped or tested since it was last marked as "unhealthy". This number is used to determine whether or not any given attempt to use an unhealthy endpoint should be skipped or tested, based on user-defined settings.

### {{endpoint_name}}:settings
This stores a hash map of settings that allow each endpoint to be customized with regard to what it considers healthy and unhealthy. These settings are all initialized to a default value when an endpoint is used for the first time. They can be customized to any other desired value by either accessing the Redis server directly, or using the `update_settings` method on the `Endpoint` class included in this project. Each setting, its purpose, and its default value is described below.

* **failure_threshold**: This should be a number between 0 and 1, and represents a percentage. If the success percentage of the endpoint's history falls below this number, the endpoint will be marked as unhealthy. Defaults to `0.95`.

* **recovery_threshold**: Similar to the above, this is also a number between 0 and 1 and represents a percentage. This number is used when an endpoint is already unhealthy, and its test history is checked to determine if it has recovered. If the success percentage of the test history is greater than or equal to this number, the endpoint will be marked as healthy. Defaults to `0.95`.

* **max_history_size**: An integer that defines the largest number of usage attempts that should be stored in an endpoint's history list. Defaults to `1000`.

* **min_history_size**: An integer that defines the minimum number of usage attempts that must be in an endpoint's history before a health check is performed. Defaults to `100`.

* **test_history_size**: An integer that defines the number of test usage attempts that should be stored in an endpoint's test history list. It functions as both a minimum and a maximum, health checks will not be performed using the test history until this number is reached, and the test history will store only this number of usage attempts. Defaults to `100`.

* **test_skip_size**: The number of times to skip over this endpoint while it is unhealthy before moving it to a "testing" status. Defaults to `1000`.

* **test_group_size**: The number of times to perform a test on this endpoint while it is unhealthy before removing it from "testing" status and resuming skipping it. Defaults to `5`.

## Local development setup
This project is intended to function in both Python 2 and 3. As such, setup will create two separate virtual environments so that any code changes you make can be tested in each. To set up your virtual environments, `cd` into the root of this project and run:

1. `virtualenv envs/python2/ -p python2`
1. `virtualenv envs/python3/ -p python3`

Once these have been created, activate each using `source envs/python{version}/bin/activate`, and install the requirements for each with `pip install -r envs/python{version}/requirements.txt`.
