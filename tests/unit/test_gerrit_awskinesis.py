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

import json
import os
import time

import boto3
from moto import mock_aws

import tests.base
from tests.base import (
    ZuulTestCase,
    iterate_timeout,
    okay_tracebacks,
    simple_layout,
)


FIXTURE_DIR = os.path.join(tests.base.FIXTURE_DIR, 'gerrit')


def serialize(event):
    return json.dumps(event).encode('utf8')


class TestGerritEventSourceAWSKinesis(ZuulTestCase):
    config_file = 'zuul-gerrit-awskinesis.conf'
    mock_aws = mock_aws()

    def setUp(self):
        self.mock_aws.start()

        self.kinesis_client = boto3.client('kinesis', region_name='us-west-2')
        self.kinesis_client.create_stream(
            StreamName='gerrit',
            ShardCount=4,
            StreamModeDetails={
                'StreamMode': 'ON_DEMAND'
            }
        )
        self.addCleanup(self.mock_aws.stop)
        super().setUp()

    @simple_layout('layouts/simple.yaml')
    def test_kinesis(self):
        listener = self.fake_gerrit.event_thread

        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')

        self.kinesis_client.put_record(
            StreamName='gerrit',
            Data=serialize(A.getPatchsetCreatedEvent(1)),
            PartitionKey='whatever',
        )

        for _ in iterate_timeout(60, 'wait for event'):
            if listener._event_count == 1:
                break
            time.sleep(0.2)
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1')
        ])
        self.assertEqual(A.reported, 1, "A should be reported")

        # Stop the listener
        listener.stop()
        listener.join()

        # Add new gerrit events while we are "offline"
        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B')
        self.kinesis_client.put_record(
            StreamName='gerrit',
            Data=serialize(B.getPatchsetCreatedEvent(1)),
            PartitionKey='whatever',
        )

        # Restart the listener
        listener.init()
        listener.start()

        for _ in iterate_timeout(60, 'wait for caught up'):
            if all(listener._caught_up.values()):
                break
            time.sleep(0.2)
        self.waitUntilSettled()

        # Make sure we don't reprocess old events (change A), but do
        # see new events (change B)
        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1'),
            dict(name='check-job', result='SUCCESS', changes='2,1'),
        ])
        self.assertEqual(A.reported, 1, "A should be reported")
        self.assertEqual(B.reported, 1, "B should be reported")

    @simple_layout('layouts/simple.yaml')
    @okay_tracebacks("invalid literal for int() with base 10: 'nope'")
    def test_kinesis_bad_checkpoint(self):
        listener = self.fake_gerrit.event_thread

        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')

        self.kinesis_client.put_record(
            StreamName='gerrit',
            Data=serialize(A.getPatchsetCreatedEvent(1)),
            PartitionKey='whatever',
        )

        for _ in iterate_timeout(60, 'wait for event'):
            if listener._event_count == 1:
                break
            time.sleep(0.2)
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1')
        ])
        self.assertEqual(A.reported, 1, "A should be reported")

        # Stop the listener
        listener.stop()
        listener.join()

        # Corrupt the checkpoint
        for cp in listener.checkpoints.values():
            cp.set("nope")

        # Add new gerrit events while we are "offline"
        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B')
        self.kinesis_client.put_record(
            StreamName='gerrit',
            Data=serialize(B.getPatchsetCreatedEvent(1)),
            PartitionKey='whatever',
        )

        # Restart the listener
        listener.init()
        listener.start()

        for _ in iterate_timeout(60, 'wait for caught up'):
            if all(listener._caught_up.values()):
                break
            time.sleep(0.2)
        self.waitUntilSettled()

        # Make sure we don't reprocess old events (change A),
        # and also that we missed change B because of the corruption
        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1'),
        ])
        self.assertEqual(A.reported, 1, "A should be reported")
        self.assertEqual(B.reported, 0, "B should not be reported")

        # Poke B again to make sure we get new events
        self.kinesis_client.put_record(
            StreamName='gerrit',
            Data=serialize(B.getPatchsetCreatedEvent(1)),
            PartitionKey='whatever',
        )

        for _ in iterate_timeout(60, 'wait for event'):
            if listener._event_count == 2:
                break
            time.sleep(0.2)
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1'),
            dict(name='check-job', result='SUCCESS', changes='2,1'),
        ])
        self.assertEqual(A.reported, 1, "A should be reported")
        self.assertEqual(B.reported, 1, "B should be reported")
