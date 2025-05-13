# Copyright 2023 Acme Gating, LLC
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

import fixtures
import json
import os
import queue
import time
import threading

import google.api_core.exceptions

import tests.base
from tests.base import (
    ZuulTestCase,
    iterate_timeout,
    okay_tracebacks,
    simple_layout,
)


FIXTURE_DIR = os.path.join(tests.base.FIXTURE_DIR, 'gerrit')


class FakePubsubMessage:
    def __init__(self, data):
        self.data = data
        self._acked = False

    def ack(self):
        self._acked = True


class FakePubsubFuture:
    def __init__(self):
        self.event = threading.Event()
        self._error = None

    def result(self):
        self.event.wait()
        if self._error:
            raise self._error

    def cancel(self, error=None):
        self._error = error
        self.event.set()


class FakePubsubSubscriber:
    def __init__(self, credentials=None):
        self.credentials = credentials
        self._queue = queue.Queue()
        self._closed = False
        self._entered = False

    def put(self, data):
        self._queue.put(data)

    def create_subscription(self, name=None, topic=None):
        if not self._entered:
            raise Exception("Attempt to use subscriber "
                            "outside of context manager")
        self._name = name
        self._topic = topic
        raise google.api_core.exceptions.AlreadyExists("Exists")

    def subscribe(self, name, callback):
        if self._closed:
            raise Exception("Attempt to use closed subscriber")
        if not self._entered:
            raise Exception("Attempt to use subscriber "
                            "outside of context manager")
        assert self._name == name
        self._callback = callback
        self._future = FakePubsubFuture()
        self._thread = threading.Thread(target=self._run)
        self._thread.start()
        return self._future

    def _run(self):
        while not self._closed:
            data = self._queue.get()
            self._queue.task_done()
            if data is None:
                continue
            msg = FakePubsubMessage(data)
            self._callback(msg)

    def __enter__(self):
        self._entered = True
        return self

    def __exit__(self, *args, **kw):
        self._closed = True
        self._queue.put(None)


def serialize(event):
    return json.dumps(event)


class TestGerritEventSourceGcloudPubsub(ZuulTestCase):
    config_file = 'zuul-gerrit-gcloud.conf'

    def setUp(self):
        self.useFixture(fixtures.MonkeyPatch(
            'zuul.driver.gerrit.gerriteventgcloudpubsub.'
            'pubsub_v1.SubscriberClient',
            FakePubsubSubscriber))
        super().setUp()

    @simple_layout('layouts/simple.yaml')
    @okay_tracebacks('Test error')
    def test_gcloud_pubsub(self):
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        subscriber = self.fake_gerrit.event_thread.subscriber
        self.fake_gerrit.event_thread.RECONNECTION_DELAY = 1

        # Assert we passed the required config entries
        self.assertEqual('projects/testproject/subscriptions/zuul',
                         subscriber._name)
        self.assertEqual('projects/testproject/topics/gerrit',
                         subscriber._topic)

        # Exercise reconnection
        err = Exception("Test error")
        subscriber._future.cancel(err)

        for _ in iterate_timeout(60, 'wait for reconnect'):
            if subscriber is not self.fake_gerrit.event_thread.subscriber:
                break
            time.sleep(0.2)

        subscriber = self.fake_gerrit.event_thread.subscriber
        self.additional_event_queues.append(subscriber._queue)

        subscriber.put(serialize(A.getPatchsetCreatedEvent(1)))
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1')
        ])
        self.assertEqual(A.reported, 1, "A should be reported")

        self.assertTrue(subscriber._queue.empty())
