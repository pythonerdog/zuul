# Copyright 2017 Red Hat, Inc.
# Copyright 2023-2024 Acme Gating, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# Utility methods to promote consistent configuration among drivers.

import concurrent
import os
import threading
import time

import voluptuous as vs

from zuul.configloader import ZUUL_REGEX, make_regex  # noqa


def time_to_seconds(s):
    if s.endswith('s'):
        return int(s[:-1])
    if s.endswith('m'):
        return int(s[:-1]) * 60
    if s.endswith('h'):
        return int(s[:-1]) * 60 * 60
    if s.endswith('d'):
        return int(s[:-1]) * 24 * 60 * 60
    if s.endswith('w'):
        return int(s[:-1]) * 7 * 24 * 60 * 60
    raise Exception("Unable to parse time value: %s" % s)


def scalar_or_list(x):
    return vs.Any([x], x)


def to_list(item):
    if not item:
        return []
    if isinstance(item, list):
        return item
    return [item]


class RateLimitInstance:
    def __init__(self, limiter, logger, msg):
        self.limiter = limiter
        self.logger = logger
        self.msg = msg

    def __enter__(self):
        self.delay = self.limiter._enter()
        self.start_time = time.monotonic()

    def __exit__(self, etype, value, tb):
        end_time = time.monotonic()
        self.limiter._exit(etype, value, tb)
        self.logger("%s in %ss after %ss delay",
                    self.msg,
                    end_time - self.start_time,
                    self.delay)


class RateLimiter:
    """A Rate limiter

    :param str name: The provider name; used in logging.
    :param float rate_limit: The rate limit expressed in
        requests per second.

    Example:
    .. code:: python

        rate_limiter = RateLimiter('provider', 1.0)
        with rate_limiter:
            api_call()

    You can optionally use the limiter as a callable in which case it
    will log a supplied message with timing information.

    .. code:: python

        rate_limiter = RateLimiter('provider', 1.0)
        with rate_limiter(log.debug, "an API call"):
            api_call()

    """

    def __init__(self, name, rate_limit):
        self._running = True
        self.name = name
        if not rate_limit:
            self.delta = 0.0
        else:
            self.delta = 1.0 / rate_limit
        self.last_ts = None
        self.lock = threading.Lock()

    def __call__(self, logmethod, msg):
        return RateLimitInstance(self, logmethod, msg)

    def __enter__(self):
        self._enter()

    def _enter(self):
        with self.lock:
            total_delay = 0.0
            if self.last_ts is None:
                self.last_ts = time.monotonic()
                return total_delay
            while True:
                now = time.monotonic()
                delta = now - self.last_ts
                if delta >= self.delta:
                    break
                delay = self.delta - delta
                time.sleep(delay)
                total_delay += delay
            self.last_ts = time.monotonic()
            return total_delay

    def __exit__(self, etype, value, tb):
        self._exit(etype, value, tb)

    def _exit(self, etype, value, tb):
        pass


class LazyExecutorTTLCache:
    """This is a lazy executor TTL cache.

    It's lazy because if it has cached data, it will always return it
    instantly.

    It's executor based, which means that if a cache miss occurs, it
    will submit a task to an executor to fetch new data.

    Finally, it's a TTL cache, which means it automatically expires data.

    Since it is only expected to be used when caching provider
    resource listing methods, it assumes there will only be one entry
    and ignores arguments -- it will return the same cached data no
    matter what arguments are supplied; but it will pass on those
    arguments to the underlying method in a cache miss.

    :param numeric ttl: The cache timeout in seconds.
    :param concurrent.futures.Executor executor: An executor to use to
        update data asynchronously in case of a cache miss.
    """

    def __init__(self, ttl, executor):
        self.ttl = ttl
        self.executor = executor
        # If we have an outstanding update being run by the executor,
        # this is the future.
        self.future = None
        # The last time the underlying method completed.
        self.last_time = None
        # The last value from the underlying method.
        self.last_value = None
        # A lock to make all of this thread safe (especially to ensure
        # we don't fire off multiple updates).
        self.lock = threading.Lock()

    def __call__(self, func):
        def decorator(*args, **kw):
            with self.lock:
                now = time.monotonic()
                if self.future and self.future.done():
                    # If a previous call spawned an update, resolve
                    # that now so we can use the data.
                    try:
                        self.last_time, self.last_value = self.future.result()
                    finally:
                        # Clear the future regardless so we don't loop.
                        self.future = None
                if (self.last_time is not None and
                    now - self.last_time < self.ttl):
                    # A cache hit.
                    return self.last_value
                # The rest of the method is a cache miss.
                if self.last_time is not None:
                    if not self.future:
                        # Fire off an asynchronous update request.
                        # This second wrapper ensures that we record
                        # the time that the update is complete along
                        # with the value.
                        def func_with_time():
                            ret = func(*args, **kw)
                            now = time.monotonic()
                            return (now, ret)
                        self.future = self.executor.submit(func_with_time)
                else:
                    # This is the first time this method has been
                    # called; since we don't have any cached data, we
                    # will synchronously update the data.
                    self.last_value = func(*args, **kw)
                    self.last_time = time.monotonic()
                return self.last_value
        return decorator


class Segment:
    def __init__(self, index, offset, data):
        self.index = index
        self.offset = offset
        self.data = data


class ImageUploader:
    """
    A helper class for drivers that upload large images in chunks.
    """

    # These values probably don't need to be changed
    error_retries = 3
    concurrency = 10

    # Subclasses must implement these
    segment_size = None

    def __init__(self, endpoint, log, path, image_name, metadata):
        if self.segment_size is None:
            raise Exception("Subclass must set block size")
        self.endpoint = endpoint
        self.log = log
        self.path = path
        self.size = os.path.getsize(path)
        self.image_name = image_name
        self.metadata = metadata
        self.timeout = None

    def shouldRetryException(self, exception):
        return True

    def uploadSegment(self, segment):
        pass

    def startUpload(self):
        pass

    def finishUpload(self):
        pass

    def abortUpload(self):
        pass

    # Main API
    def upload(self, timeout=None):
        if timeout:
            self.timeout = time.monotonic() + timeout
        self.startUpload()
        try:
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.concurrency) as executor:
                with open(self.path, 'rb') as image_file:
                    self._uploadInner(executor, image_file)
            return self.finishUpload()
        except Exception:
            self.log.exception("Error uploading image:")
            self.abortUpload()

    # Subclasses can use this helper method for wrapping retryable calls
    def retry(self, func, *args, **kw):
        for x in range(self.error_retries):
            try:
                return func(*args, **kw)
            except Exception as e:
                if not self.shouldRetryException(e):
                    raise
                if x + 1 >= self.error_retries:
                    raise
                time.sleep(2 * x)

    def getTimeout(self):
        if self.timeout is None:
            return None
        return self.timeout - time.monotonic()

    def checkTimeout(self):
        if self.timeout is None:
            return
        if self.getTimeout() < 0:
            raise Exception("Timed out uploading image")

    # Internal methods
    def _uploadInner(self, executor, image_file):
        futures = set()
        for index, offset in enumerate(range(0, self.size, self.segment_size)):
            segment = Segment(index, offset,
                              image_file.read(self.segment_size))
            future = executor.submit(self.uploadSegment, segment)
            futures.add(future)
            # Keep the pool of workers supplied with data but without
            # reading the entire file into memory.
            if len(futures) >= (self.concurrency * 2):
                (done, futures) = concurrent.futures.wait(
                    futures,
                    timeout=self.getTimeout(),
                    return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    future.result()
                # Only check the timeout after waiting (not every pass
                # through the loop)
                self.checkTimeout()
        # We're done reading the file, wait for all uploads to finish
        (done, futures) = concurrent.futures.wait(
            futures,
            timeout=self.getTimeout())
        for future in done:
            future.result()
        self.checkTimeout()


class Timer:
    def __init__(self, log, msg):
        self.log = log
        self.msg = msg

    def __enter__(self):
        self.start = time.perf_counter()

    def __exit__(self, type, value, traceback):
        delta = time.perf_counter() - self.start
        self.log.debug(f'{self.msg} in {delta}')
