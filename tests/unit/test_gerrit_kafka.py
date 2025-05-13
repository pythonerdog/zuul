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

import confluent_kafka as kafka

import tests.base
from tests.base import (
    ZuulTestCase,
    iterate_timeout,
    okay_tracebacks,
    simple_layout,
)


FIXTURE_DIR = os.path.join(tests.base.FIXTURE_DIR, 'gerrit')


class FakeKafkaMessage:
    def __init__(self, topic, offset, value, error=None):
        self._topic = topic
        self._error = error
        self._offset = offset
        if error:
            self._value = None
        else:
            self._value = value

    def error(self):
        return self._error

    def value(self):
        return self._value

    def partition(self):
        return 0

    def topic(self):
        return self._topic

    def offset(self):
        return self._offset


class FakeKafkaConsumer:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.topics = None
        self._queue = queue.Queue()
        self.closed = 0
        self._offset = 0

    def put(self, data):
        self._queue.put(data)

    def subscribe(self, topics):
        self.topics = topics

    def poll(self, timeout=0):
        try:
            data = self._queue.get(timeout=timeout)
            self._queue.task_done()
            if isinstance(data, kafka.KafkaError):
                return FakeKafkaMessage(
                    'gerrit', self._offset, None, error=data)
            self._offset += 1
            return FakeKafkaMessage('gerrit', self._offset - 1, data)
        except queue.Empty:
            return None

    def close(self):
        self.closed += 1


def serialize(event):
    return json.dumps(event).encode('utf8')


class TestGerritEventSourceKafka(ZuulTestCase):
    config_file = 'zuul-gerrit-kafka.conf'

    def setUp(self):
        self.useFixture(fixtures.MonkeyPatch(
            'zuul.driver.gerrit.gerriteventkafka.kafka.Consumer',
            FakeKafkaConsumer))
        super().setUp()

    @simple_layout('layouts/simple.yaml')
    @okay_tracebacks('Broker disconnected before response received')
    def test_kafka(self):
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        consumer = self.fake_gerrit.event_thread.consumer
        self.fake_gerrit.event_thread.RECONNECTION_DELAY = 1

        # Assert we passed the required config entries
        self.assertTrue(isinstance(consumer.config, dict))
        self.assertTrue('bootstrap.servers' in consumer.config)
        self.assertTrue('group.id' in consumer.config)

        # Exercise error handling
        err = kafka.KafkaError(kafka.KafkaError._PARTITION_EOF)
        consumer.put(err)

        # Exercise reconnection
        err = kafka.KafkaError(kafka.KafkaError.NETWORK_EXCEPTION)
        consumer.put(err)

        for _ in iterate_timeout(60, 'wait for reconnect'):
            if consumer is not self.fake_gerrit.event_thread.consumer:
                break
            time.sleep(0.2)

        consumer = self.fake_gerrit.event_thread.consumer
        self.additional_event_queues.append(consumer._queue)

        consumer.put(serialize(A.getPatchsetCreatedEvent(1)))
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1')
        ])
        self.assertEqual(A.reported, 1, "A should be reported")

        self.assertTrue(consumer._queue.empty())
