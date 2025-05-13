# Copyright 2024 Acme Gating, LLC
# Copyright 2024 BMW Group
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

import math
import os
import textwrap
import time
import uuid
from collections import defaultdict
from unittest import mock

from zuul import exceptions
from zuul import model
import zuul.driver.aws.awsendpoint
from zuul.launcher.client import LauncherClient

import responses
import testtools
import yaml
from kazoo.exceptions import NoNodeError
from moto import mock_aws
import moto.ec2.responses.instances
import boto3

from tests.base import (
    ResponsesFixture,
    ZuulTestCase,
    driver_config,
    iterate_timeout,
    okay_tracebacks,
    return_data,
    simple_layout,
)
from tests.fake_nodescan import (
    FakeSocket,
    FakePoll,
    FakeTransport,
)


class ImageMocksFixture(ResponsesFixture):
    def __init__(self):
        super().__init__()
        raw_body = 'test raw image'
        zst_body = b'(\xb5/\xfd\x04Xy\x00\x00test raw image\n\xde\x9d\x9c\xfb'
        qcow2_body = "test qcow2 image"
        self.requests_mock.add_passthru("http://localhost")
        self.requests_mock.add(
            responses.GET,
            'http://example.com/image.raw',
            body=raw_body)
        self.requests_mock.add(
            responses.GET,
            'http://example.com/image.raw.zst',
            body=zst_body)
        self.requests_mock.add(
            responses.GET,
            'http://example.com/image.qcow2',
            body=qcow2_body)
        self.requests_mock.add(
            responses.HEAD,
            'http://example.com/image.raw',
            headers={'content-length': str(len(raw_body))})
        self.requests_mock.add(
            responses.HEAD,
            'http://example.com/image.raw.zst',
            headers={'content-length': str(len(zst_body))})
        self.requests_mock.add(
            responses.HEAD,
            'http://example.com/image.qcow2',
            headers={'content-length': str(len(qcow2_body))})
        # The next three are for the signed_url test
        # Partial response
        self.requests_mock.add(
            responses.GET,
            'http://example.com/getonly.raw',
            match=[responses.matchers.header_matcher({"Range": "bytes=0-0"})],
            status=206,
            headers={'content-length': '1',
                     'content-range': f'bytes 0-0/{len(raw_body)}'},
        )
        # The full response
        self.requests_mock.add(
            responses.GET,
            'http://example.com/getonly.raw',
            headers={'content-length': str(len(raw_body))})
        # Head doesn't work
        self.requests_mock.add(
            responses.HEAD,
            'http://example.com/getonly.raw',
            status=403)


class LauncherBaseTestCase(ZuulTestCase):
    config_file = 'zuul-connections-nodepool.conf'
    mock_aws = mock_aws()
    debian_return_data = {
        'zuul': {
            'artifacts': [
                {
                    'name': 'raw image',
                    'url': 'http://example.com/image.raw.zst',
                    'metadata': {
                        'type': 'zuul_image',
                        'image_name': 'debian-local',
                        'format': 'raw',
                        'sha256': ('d043e8080c82dbfeca3199a24d5f0193'
                                   'e66755b5ba62d6b60107a248996a6795'),
                        'md5sum': '78d2d3ff2463bc75c7cc1d38b8df6a6b',
                    }
                }, {
                    'name': 'qcow2 image',
                    'url': 'http://example.com/image.qcow2',
                    'metadata': {
                        'type': 'zuul_image',
                        'image_name': 'debian-local',
                        'format': 'qcow2',
                        'sha256': ('59984dd82f51edb3777b969739a92780'
                                   'a520bb314b8d64b294d5de976bd8efb9'),
                        'md5sum': '262278e1632567a907e4604e9edd2e83',
                    }
                },
            ]
        }
    }
    ubuntu_return_data = {
        'zuul': {
            'artifacts': [
                {
                    'name': 'raw image',
                    'url': 'http://example.com/image.raw.zst',
                    'metadata': {
                        'type': 'zuul_image',
                        'image_name': 'ubuntu-local',
                        'format': 'raw',
                        'sha256': ('d043e8080c82dbfeca3199a24d5f0193'
                                   'e66755b5ba62d6b60107a248996a6795'),
                        'md5sum': '78d2d3ff2463bc75c7cc1d38b8df6a6b',
                    }
                }, {
                    'name': 'qcow2 image',
                    'url': 'http://example.com/image.qcow2',
                    'metadata': {
                        'type': 'zuul_image',
                        'image_name': 'ubuntu-local',
                        'format': 'qcow2',
                        'sha256': ('59984dd82f51edb3777b969739a92780'
                                   'a520bb314b8d64b294d5de976bd8efb9'),
                        'md5sum': '262278e1632567a907e4604e9edd2e83',
                    }
                },
            ]
        }
    }

    def setUp(self):
        self.initTestConfig()

        # Patch moto describe_instances as it isn't terribly threadsafe
        orig_describe_instances = \
            moto.ec2.responses.instances.InstanceResponse.describe_instances

        def describe_instances(self):
            for x in range(10):
                try:
                    return orig_describe_instances(self)
                except RuntimeError:
                    # describe_instances can fail if the reservations dict
                    # changes while it renders its template. Ignore the
                    # error and retry.
                    pass
        self.patch(moto.ec2.responses.instances.InstanceResponse,
                   'describe_instances',
                   describe_instances)

        self.mock_aws.start()
        # Must start responses after mock_aws
        self.useFixture(ImageMocksFixture())
        self.s3 = boto3.resource('s3', region_name='us-east-1')
        self.s3.create_bucket(Bucket='zuul')
        self.addCleanup(self.mock_aws.stop)
        self.patch(zuul.driver.aws.awsendpoint, 'CACHE_TTL', 1)

        quotas = {}
        quotas.update(self.test_config.driver.test_launcher.get(
            'quotas', {}))

        def getQuotaLimits(self):
            return model.QuotaInformation(default=math.inf, **quotas)
        self.patch(zuul.driver.aws.awsprovider.AwsProvider,
                   'getQuotaLimits',
                   getQuotaLimits)
        super().setUp()

    def getNodes(self, request):
        nodes = []
        for node in self.launcher.api.nodes_cache.getItems():
            if node.request_id == request.uuid:
                nodes.append(node)
        return nodes

    def _nodes_by_label(self):
        nodes = self.launcher.api.nodes_cache.getItems()
        nodes_by_label = defaultdict(list)
        for node in nodes:
            nodes_by_label[node.label].append(node)
        return nodes_by_label


class TestLauncher(LauncherBaseTestCase):

    def _waitForArtifacts(self, image_name, count):
        for _ in iterate_timeout(30, "artifacts to settle"):
            artifacts = self.launcher.image_build_registry.\
                getArtifactsForImage(image_name)
            if len(artifacts) == count:
                return artifacts

    @simple_layout('layouts/nodepool-missing-connection.yaml',
                   enable_nodepool=True)
    def test_launcher_missing_connection(self):
        tenant = self.scheds.first.sched.abide.tenants.get("tenant-one")
        errors = tenant.layout.loading_errors
        self.assertEqual(len(errors), 1)

        idx = 0
        self.assertEqual(errors[idx].severity, model.SEVERITY_ERROR)
        self.assertEqual(errors[idx].name, 'Unknown Connection')
        self.assertIn('provider stanza', errors[idx].error)

    @simple_layout('layouts/nodepool-image.yaml', enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @return_data(
        'build-ubuntu-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.ubuntu_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsProviderEndpoint.uploadImage',
                return_value="test_external_id")
    def test_launcher_missing_image_build(self, mock_uploadImage):
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))

        for _ in iterate_timeout(
                30, "scheduler and launcher to have the same layout"):
            if (self.scheds.first.sched.local_layout_state.get("tenant-one") ==
                self.launcher.local_layout_state.get("tenant-one")):
                break

        # The build should not run again because the image is no
        # longer missing
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)
        for name in [
                'review.example.com%2Forg%2Fcommon-config/debian-local',
                'review.example.com%2Forg%2Fcommon-config/ubuntu-local',
        ]:
            artifacts = self._waitForArtifacts(name, 1)
            self.assertEqual('raw', artifacts[0].format)
            self.assertTrue(artifacts[0].validated)
            uploads = self.launcher.image_upload_registry.getUploadsForImage(
                name)
            self.assertEqual(1, len(uploads))
            self.assertEqual(artifacts[0].uuid, uploads[0].artifact_uuid)
            self.assertEqual("test_external_id", uploads[0].external_id)
            self.assertTrue(uploads[0].validated)

    @simple_layout('layouts/nodepool-image.yaml', enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @return_data(
        'build-ubuntu-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.ubuntu_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsProviderEndpoint.uploadImage',
                return_value="test_external_id")
    def test_launcher_image_expire(self, mock_uploadImage):
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))

        for _ in iterate_timeout(
                30, "scheduler and launcher to have the same layout"):
            if (self.scheds.first.sched.local_layout_state.get("tenant-one") ==
                self.launcher.local_layout_state.get("tenant-one")):
                break

        # The build should not run again because the image is no
        # longer missing
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)
        for name in [
                'review.example.com%2Forg%2Fcommon-config/debian-local',
                'review.example.com%2Forg%2Fcommon-config/ubuntu-local',
        ]:
            artifacts = self._waitForArtifacts(name, 1)
            self.assertEqual('raw', artifacts[0].format)
            self.assertTrue(artifacts[0].validated)
            uploads = self.launcher.image_upload_registry.getUploadsForImage(
                name)
            self.assertEqual(1, len(uploads))
            self.assertEqual(artifacts[0].uuid, uploads[0].artifact_uuid)
            self.assertEqual("test_external_id", uploads[0].external_id)
            self.assertTrue(uploads[0].validated)

        image_cname = 'review.example.com%2Forg%2Fcommon-config/ubuntu-local'
        # Run another build event manually
        driver = self.launcher.connections.drivers['zuul']
        event = driver.getImageBuildEvent(
            ['ubuntu-local'], 'review.example.com',
            'org/common-config', 'master')
        self.launcher.trigger_events['tenant-one'].put(
            event.trigger_name, event)
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)
        self._waitForArtifacts(image_cname, 2)

        # Run another build event manually
        driver = self.launcher.connections.drivers['zuul']
        event = driver.getImageBuildEvent(
            ['ubuntu-local'], 'review.example.com',
            'org/common-config', 'master')
        self.launcher.trigger_events['tenant-one'].put(
            event.trigger_name, event)
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)
        self._waitForArtifacts(image_cname, 3)

        # Trigger a deletion run
        self.launcher.upload_deleted_event.set()
        self.launcher.wake_event.set()
        self._waitForArtifacts(image_cname, 2)

    @simple_layout('layouts/nodepool-image-no-validate.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsProviderEndpoint.uploadImage',
                return_value="test_external_id")
    def test_launcher_image_no_validation(self, mock_uploadimage):
        # Test a two-stage image-build where we don't actually run the
        # validate stage (so all artifacts should be un-validated).
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
        ])
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))

        for _ in iterate_timeout(
                30, "scheduler and launcher to have the same layout"):
            if (self.scheds.first.sched.local_layout_state.get("tenant-one") ==
                self.launcher.local_layout_state.get("tenant-one")):
                break

        # The build should not run again because the image is no
        # longer missing
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
        ])
        name = 'review.example.com%2Forg%2Fcommon-config/debian-local'
        artifacts = self._waitForArtifacts(name, 1)
        self.assertEqual('raw', artifacts[0].format)
        self.assertFalse(artifacts[0].validated)
        uploads = self.launcher.image_upload_registry.getUploadsForImage(
            name)
        self.assertEqual(1, len(uploads))
        self.assertEqual(artifacts[0].uuid, uploads[0].artifact_uuid)
        self.assertEqual("test_external_id", uploads[0].external_id)
        self.assertFalse(uploads[0].validated)

    @simple_layout('layouts/nodepool-image-validate.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsProviderEndpoint.uploadImage',
                return_value="test_external_id")
    def test_launcher_image_validation(self, mock_uploadImage):
        # Test a two-stage image-build where we do run the validate
        # stage.
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='validate-debian-local-image', result='SUCCESS'),
        ])
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))

        for _ in iterate_timeout(
                30, "scheduler and launcher to have the same layout"):
            if (self.scheds.first.sched.local_layout_state.get("tenant-one") ==
                self.launcher.local_layout_state.get("tenant-one")):
                break

        # The build should not run again because the image is no
        # longer missing
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='validate-debian-local-image', result='SUCCESS'),
        ])
        name = 'review.example.com%2Forg%2Fcommon-config/debian-local'
        artifacts = self._waitForArtifacts(name, 1)
        self.assertEqual('raw', artifacts[0].format)
        self.assertFalse(artifacts[0].validated)
        uploads = self.launcher.image_upload_registry.getUploadsForImage(
            name)
        self.assertEqual(1, len(uploads))
        self.assertEqual(artifacts[0].uuid, uploads[0].artifact_uuid)
        self.assertEqual("test_external_id", uploads[0].external_id)
        self.assertTrue(uploads[0].validated)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    @mock.patch('zuul.driver.aws.awsendpoint.AwsProviderEndpoint.uploadImage',
                return_value="test_external_id")
    def test_launcher_crashed_upload(self, mock_uploadImage):
        self.waitUntilSettled()
        provider = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-main')
        endpoint = provider.getEndpoint()
        image = list(provider.images.values())[0]
        # create an IBA and an upload
        with self.createZKContext(None) as ctx:
            # This starts with an unknown state, then
            # createImageUploads will set it to ready.
            iba = model.ImageBuildArtifact.new(
                ctx,
                uuid='iba-uuid',
                name=image.name,
                canonical_name=image.canonical_name,
                project_canonical_name=image.project_canonical_name,
                url='http://example.com/image.raw.zst',
                timestamp=time.time(),
            )
            with iba.locked(self.zk_client):
                model.ImageUpload.new(
                    ctx,
                    uuid='upload-uuid',
                    artifact_uuid='iba-uuid',
                    endpoint_name=endpoint.canonical_name,
                    providers=[provider.canonical_name],
                    canonical_name=image.canonical_name,
                    timestamp=time.time(),
                    _state=model.ImageUpload.State.UPLOADING,
                    state_time=time.time(),
                )
                with iba.activeContext(ctx):
                    iba.state = iba.State.READY
        self.waitUntilSettled()
        pending_uploads = [
            u for u in self.launcher.image_upload_registry.getItems()
            if u.state == u.State.PENDING]
        self.assertEqual(0, len(pending_uploads))

    getonly_return_data = {
        'zuul': {
            'artifacts': [
                {
                    'name': 'raw image',
                    'url': 'http://example.com/getonly.raw?Dummy-Token=foo',
                    'metadata': {
                        'type': 'zuul_image',
                        'image_name': 'debian-local',
                        'format': 'raw',
                        'sha256': ('d043e8080c82dbfeca3199a24d5f0193'
                                   'e66755b5ba62d6b60107a248996a6795'),
                        'md5sum': '78d2d3ff2463bc75c7cc1d38b8df6a6b',
                    }
                },
            ]
        }
    }

    @simple_layout('layouts/nodepool-image.yaml', enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        getonly_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsProviderEndpoint.uploadImage',
                return_value="test_external_id")
    def test_launcher_image_signed_url(self, mock_uploadImage):
        # If the image is uploaded using a signed url, it will not
        # permit a HEAD request; this tests the GET range fallback.

        self.waitUntilSettled()
        self.log.debug("JEB wake")
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)
        name = 'review.example.com%2Forg%2Fcommon-config/debian-local'
        artifacts = self._waitForArtifacts(name, 1)
        self.assertEqual('raw', artifacts[0].format)
        self.assertTrue(artifacts[0].validated)
        uploads = self.launcher.image_upload_registry.getUploadsForImage(
            name)
        self.assertEqual(1, len(uploads))
        self.assertEqual(artifacts[0].uuid, uploads[0].artifact_uuid)
        self.assertEqual("test_external_id", uploads[0].external_id)
        self.assertTrue(uploads[0].validated)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_jobs_executed(self):
        self.executor_server.hold_jobs_in_build = True

        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        nodes = self.launcher.api.nodes_cache.getItems()
        self.assertEqual(nodes[0].host_keys, [])

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual(self.getJobFromHistory('check-job').result,
                         'SUCCESS')
        self.assertEqual(A.data['status'], 'MERGED')
        self.assertEqual(A.reported, 2)
        self.assertEqual(self.getJobFromHistory('check-job').node,
                         'debian-normal')
        pname = 'review_example_com%2Forg%2Fcommon-config/aws-us-east-1-main'
        self.assertReportedStat(
            f'zuul.provider.{pname}.nodes.state.requested',
            kind='g')
        self.assertReportedStat(
            f'zuul.provider.{pname}.label.debian-normal.nodes.state.requested',
            kind='g')
        self.assertReportedStat(
            'zuul.nodes.state.requested',
            kind='g')

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_canceled_request(self):
        # Test that a canceled request is cleaned up
        self.hold_jobs_in_queue = True
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        queue = list(self.executor_api.queued())
        self.assertEqual(len(self.builds), 0)
        self.assertEqual(len(queue), 1)

        self.fake_gerrit.addEvent(A.getChangeAbandonedEvent())

        self.waitUntilSettled()
        self.assertHistory([])
        reqs = self.launcher.api.getNodesetRequests()
        self.assertEqual(0, len(reqs))

    @simple_layout('layouts/nodepool-empty-nodeset.yaml', enable_nodepool=True)
    def test_empty_nodeset(self):
        self.executor_server.hold_jobs_in_build = True

        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual(self.getJobFromHistory('check-job').result,
                         'SUCCESS')
        self.assertEqual(A.data['status'], 'MERGED')
        self.assertEqual(A.reported, 2)
        self.assertEqual(self.getJobFromHistory('check-job').node,
                         None)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_launcher_failover(self):
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)

        with mock.patch(
            'zuul.driver.aws.awsendpoint.AwsProviderEndpoint._refresh'
        ) as refresh_mock:
            # Patch 'endpoint._refresh()' to return w/o updating
            refresh_mock.side_effect = lambda o: o
            self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
            for _ in iterate_timeout(10, "node is building"):
                nodes = self.launcher.api.nodes_cache.getItems()
                if not nodes:
                    continue
                if all(
                    n.create_state and
                    n.create_state[
                        "state"] == n.create_state_machine.INSTANCE_CREATING
                    for n in nodes
                ):
                    break
            self.launcher.stop()
            self.launcher.join()

            self.launcher = self.createLauncher()

        self.waitUntilSettled()
        self.assertEqual(self.getJobFromHistory('check-job').result,
                         'SUCCESS')
        self.assertEqual(A.data['status'], 'MERGED')
        self.assertEqual(A.reported, 2)
        self.assertEqual(self.getJobFromHistory('check-job').node,
                         'debian-normal')

    @simple_layout('layouts/nodepool-untrusted-conf.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsProviderEndpoint.uploadImage',
                return_value="test_external_id")
    def test_launcher_untrusted_project(self, mock_uploadImage):
        # Test that we can add all the configuration in an untrusted
        # project (most other tests just do everything in a
        # config-project).

        in_repo_conf = textwrap.dedent(
            """
            - image: {'name': 'debian-local', 'type': 'zuul'}
            - flavor: {'name': 'normal'}
            - label:
                name: debian-local-normal
                image: debian-local
                flavor: normal
            - section:
                name: aws-us-east-1
                connection: aws
                region: us-east-1
                boot-timeout: 120
                launch-timeout: 600
                object-storage:
                  bucket-name: zuul
                flavors:
                  - name: normal
                    instance-type: t3.medium
                images:
                  - name: debian-local
            - provider:
                name: aws-us-east-1-main
                section: aws-us-east-1
                labels:
                  - name: debian-local-normal
                    key-name: zuul
            """)

        file_dict = {'zuul.d/images.yaml': in_repo_conf}
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A',
                                           files=file_dict)
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='test-job', result='SUCCESS', changes='1,1'),
        ], ordered=False)
        self.assertEqual(A.data['status'], 'MERGED')
        self.fake_gerrit.addEvent(A.getChangeMergedEvent())
        self.waitUntilSettled()

        in_repo_conf = textwrap.dedent(
            """
            - job:
                name: build-debian-local-image
                image-build-name: debian-local
            - project:
                check:
                  jobs:
                    - build-debian-local-image
                gate:
                  jobs:
                    - build-debian-local-image
                image-build:
                  jobs:
                    - build-debian-local-image
            """)
        file_dict = {'zuul.d/image-jobs.yaml': in_repo_conf}
        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B',
                                           files=file_dict)
        B.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(B.addApproval('Approved', 1))
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='test-job', result='SUCCESS', changes='1,1'),
            dict(name='test-job', result='SUCCESS', changes='2,1'),
            dict(name='build-debian-local-image', result='SUCCESS',
                 changes='2,1'),
        ], ordered=False)
        self.assertEqual(B.data['status'], 'MERGED')
        self.fake_gerrit.addEvent(B.getChangeMergedEvent())
        self.waitUntilSettled()

        for _ in iterate_timeout(
                30, "scheduler and launcher to have the same layout"):
            if (self.scheds.first.sched.local_layout_state.get("tenant-one") ==
                self.launcher.local_layout_state.get("tenant-one")):
                break

        # The build should not run again because the image is no
        # longer missing
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='test-job', result='SUCCESS', changes='1,1'),
            dict(name='test-job', result='SUCCESS', changes='2,1'),
            dict(name='build-debian-local-image', result='SUCCESS',
                 changes='2,1'),
            dict(name='build-debian-local-image', result='SUCCESS',
                 ref='refs/heads/master'),
        ], ordered=False)
        for name in [
                'review.example.com%2Forg%2Fproject/debian-local',
        ]:
            artifacts = self._waitForArtifacts(name, 1)
            self.assertEqual('raw', artifacts[0].format)
            self.assertTrue(artifacts[0].validated)
            uploads = self.launcher.image_upload_registry.getUploadsForImage(
                name)
            self.assertEqual(1, len(uploads))
            self.assertEqual(artifacts[0].uuid, uploads[0].artifact_uuid)
            self.assertEqual("test_external_id", uploads[0].external_id)
            self.assertTrue(uploads[0].validated)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_launcher_missing_label(self):
        ctx = self.createZKContext(None)
        labels = ["debian-normal", "debian-unavailable"]
        request = self.requestNodes(labels)
        self.assertEqual(request.state, model.NodesetRequest.State.FAILED)
        self.assertEqual(len(request.nodes), 0)

        request.delete(ctx)
        self.waitUntilSettled()

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_lost_nodeset_request(self):
        ctx = self.createZKContext(None)
        request = self.requestNodes(["debian-normal"])

        provider_nodes = []
        for node_id in request.nodes:
            provider_nodes.append(model.ProviderNode.fromZK(
                ctx, path=model.ProviderNode._getPath(node_id)))

        request.delete(ctx)
        self.waitUntilSettled()

        with testtools.ExpectedException(NoNodeError):
            # Request should be gone
            request.refresh(ctx)

        for pnode in provider_nodes:
            for _ in iterate_timeout(60, "node to be deallocated"):
                pnode.refresh(ctx)
                if pnode.request_id is None:
                    break

        request = self.requestNodes(["debian-normal"])
        self.waitUntilSettled()
        # Node should be re-used as part of the new request
        self.assertEqual(set(request.nodes), {n.uuid for n in provider_nodes})

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    @okay_tracebacks('_getQuotaForInstanceType')
    def test_failed_node(self):
        # Test a node failure outside of the create state machine
        ctx = self.createZKContext(None)
        request = self.requestNodes(["debian-invalid"])
        self.assertEqual(request.state, model.NodesetRequest.State.FAILED)
        provider_node_data = request.provider_node_data[0]
        self.assertEqual(len(provider_node_data['failed_providers']), 1)
        self.assertEqual(len(request.nodes), 1)

        provider_nodes = []
        for node_id in request.nodes:
            provider_nodes.append(model.ProviderNode.fromZK(
                ctx, path=model.ProviderNode._getPath(node_id)))

        request.delete(ctx)
        self.waitUntilSettled()

        for pnode in provider_nodes:
            for _ in iterate_timeout(60, "node to be deleted"):
                try:
                    pnode.refresh(ctx)
                except NoNodeError:
                    break

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    @mock.patch(
        'zuul.driver.aws.awsendpoint.AwsProviderEndpoint._createInstance',
        side_effect=Exception("Fake error"))
    @okay_tracebacks('_completeCreateInstance')
    def test_failed_node2(self, mock_createInstance):
        # Test a node failure inside the create state machine
        ctx = self.createZKContext(None)
        request = self.requestNodes(["debian-normal"])
        self.assertEqual(request.state, model.NodesetRequest.State.FAILED)
        provider_node_data = request.provider_node_data[0]
        self.assertEqual(len(provider_node_data['failed_providers']), 1)
        self.assertEqual(len(request.nodes), 1)

        provider_nodes = []
        for node_id in request.nodes:
            provider_nodes.append(model.ProviderNode.fromZK(
                ctx, path=model.ProviderNode._getPath(node_id)))

        request.delete(ctx)
        self.waitUntilSettled()

        for pnode in provider_nodes:
            for _ in iterate_timeout(60, "node to be deleted"):
                try:
                    pnode.refresh(ctx)
                except NoNodeError:
                    break

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    @mock.patch(
        'zuul.driver.aws.awsendpoint.AwsCreateStateMachine.advance',
        side_effect=Exception("Fake error"))
    @mock.patch(
        'zuul.driver.aws.awsendpoint.AwsDeleteStateMachine.advance',
        side_effect=Exception("Fake error"))
    @mock.patch('zuul.launcher.server.Launcher.DELETE_TIMEOUT', 1)
    @okay_tracebacks('_execute_mock_call')
    def test_failed_node3(self, mock_create, mock_delete):
        # Test a node failure inside both the create and delete state
        # machines
        ctx = self.createZKContext(None)
        request = self.requestNodes(["debian-normal"])
        self.assertEqual(request.state, model.NodesetRequest.State.FAILED)
        provider_node_data = request.provider_node_data[0]
        self.assertEqual(len(provider_node_data['failed_providers']), 1)
        self.assertEqual(len(request.nodes), 1)

        provider_nodes = []
        for node_id in request.nodes:
            provider_nodes.append(model.ProviderNode.fromZK(
                ctx, path=model.ProviderNode._getPath(node_id)))

        request.delete(ctx)
        self.waitUntilSettled()

        for pnode in provider_nodes:
            for _ in iterate_timeout(60, "node to be deleted"):
                try:
                    pnode.refresh(ctx)
                except NoNodeError:
                    break

    @simple_layout('layouts/launcher-nodeset-fallback.yaml',
                   enable_nodepool=True)
    @okay_tracebacks('_getQuotaForInstanceType')
    def test_nodeset_fallback(self):
        # Test that nodeset fallback works
        self.executor_server.hold_jobs_in_build = True

        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        job = tenant.layout.getJob('check-job')
        alts = job.flattenNodesetAlternatives(tenant.layout)
        self.assertEqual(2, len(alts))
        self.assertEqual('debian-invalid', alts[0].nodes[('node',)].label)
        self.assertEqual('debian-normal', alts[1].nodes[('node',)].label)

        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        build = self.getBuildByName('check-job')
        inv_path = os.path.join(build.jobdir.root, 'ansible', 'inventory.yaml')
        with open(inv_path, 'r') as f:
            inventory = yaml.safe_load(f)
        label = inventory['all']['hosts']['node']['nodepool']['label']
        self.assertEqual('debian-normal', label)

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual(A.data['status'], 'NEW')
        self.assertEqual(A.reported, 1)
        self.assertNotIn('NODE_FAILURE', A.messages[0])
        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1'),
        ], ordered=False)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    @mock.patch(
        'zuul.driver.aws.awsendpoint.AwsProviderEndpoint._createInstance',
        side_effect=exceptions.QuotaException)
    def test_quota_failure(self, mock_create):
        ctx = self.createZKContext(None)
        # This tests an unexpected quota error.
        # The request should never be fulfilled
        with testtools.ExpectedException(Exception):
            self.requestNodes(["debian-normal"])

        # We should have tried to build at least one node that was
        # marked as tempfail.
        requests = self.launcher.api.requests_cache.getItems()
        request = requests[0]
        self.assertTrue(isinstance(request.provider_node_data[0]['uuid'], str))
        # We can't assert anything about the node itself because it
        # will have been deleted, but we have asserted there was at
        # least an attempt.

        # Now explicitly delete the request to avoid exceptions in the
        # launcher caused by request processing attempting to relaunch the
        # node during launcher shutdown. The clean no exceptions in logs
        # check for unittests fails otherwise.
        request.delete(ctx)
        self.waitUntilSettled()

    @simple_layout('layouts/nodepool-multi-provider.yaml',
                   enable_nodepool=True)
    @driver_config('test_launcher', quotas={
        'instances': 2,
    })
    def test_provider_selection_spread(self):
        # Test that we spread quota use out among multiple providers
        self.waitUntilSettled()

        request1 = self.requestNodes(["debian-normal"])
        nodes1 = self.getNodes(request1)
        self.assertEqual(1, len(nodes1))

        request2 = self.requestNodes(["debian-normal"])
        nodes2 = self.getNodes(request2)
        self.assertEqual(1, len(nodes2))

        self.assertNotEqual(nodes1[0].provider, nodes2[0].provider)

    @simple_layout('layouts/nodepool-multi-provider.yaml',
                   enable_nodepool=True)
    @driver_config('test_launcher', quotas={
        'instances': 3,
    })
    def test_provider_selection_locality(self):
        # Test that we use the same provider for multiple nodes within
        # a request if possible.
        self.waitUntilSettled()

        request1 = self.requestNodes(["debian-normal", "debian-normal"])
        nodes1 = self.getNodes(request1)
        self.assertEqual(2, len(nodes1))

        # These can be served from either provider; both should be
        # assigned to the same one.
        self.assertEqual(nodes1[0].provider, nodes1[1].provider)

        request2 = self.requestNodes(["debian-large", "debian-small"])
        nodes2 = self.getNodes(request2)
        self.assertEqual(2, len(nodes2))

        # These are served by different providers, so they should be
        # different.
        self.assertNotEqual(nodes2[0].provider, nodes2[1].provider)
        # Sanity check since we know the actual providers.
        self.assertEqual('review.example.com%2Forg%2Fcommon-config/'
                         'aws-us-west-1-main', nodes2[0].provider)
        self.assertEqual('review.example.com%2Forg%2Fcommon-config/'
                         'aws-us-east-1-main', nodes2[1].provider)

    @simple_layout('layouts/nodepool-nodescan.yaml', enable_nodepool=True)
    @okay_tracebacks('_checkNodescanRequest')
    @mock.patch('paramiko.transport.Transport')
    @mock.patch('socket.socket')
    @mock.patch('select.epoll')
    def test_nodescan_failure(self, mock_epoll, mock_socket, mock_transport):
        # Test a nodescan failure
        fake_socket = FakeSocket()
        mock_socket.return_value = fake_socket
        mock_epoll.return_value = FakePoll()
        mock_transport.return_value = FakeTransport(_fail=True)

        ctx = self.createZKContext(None)
        request = self.requestNodes(["debian-normal"], timeout=30)
        self.assertEqual(request.state, model.NodesetRequest.State.FAILED)
        provider_node_data = request.provider_node_data[0]
        self.assertEqual(len(provider_node_data['failed_providers']), 1)
        self.assertEqual(len(request.nodes), 1)

        provider_nodes = []
        for node_id in request.nodes:
            provider_nodes.append(model.ProviderNode.fromZK(
                ctx, path=model.ProviderNode._getPath(node_id)))

        request.delete(ctx)
        self.waitUntilSettled()

        for pnode in provider_nodes:
            for _ in iterate_timeout(60, "node to be deleted"):
                try:
                    pnode.refresh(ctx)
                except NoNodeError:
                    break

    @simple_layout('layouts/nodepool-nodescan.yaml', enable_nodepool=True)
    @okay_tracebacks('_checkNodescanRequest')
    @mock.patch('paramiko.transport.Transport')
    @mock.patch('socket.socket')
    @mock.patch('select.epoll')
    def test_nodescan_success(self, mock_epoll, mock_socket, mock_transport):
        # Test a normal launch with a nodescan
        fake_socket = FakeSocket()
        mock_socket.return_value = fake_socket
        mock_epoll.return_value = FakePoll()
        mock_transport.return_value = FakeTransport()

        ctx = self.createZKContext(None)
        request = self.requestNodes(["debian-normal"])
        self.assertEqual(request.state, model.NodesetRequest.State.FULFILLED)
        provider_node_data = request.provider_node_data[0]
        self.assertEqual(len(provider_node_data['failed_providers']), 0)
        self.assertEqual(len(request.nodes), 1)

        node = model.ProviderNode.fromZK(
            ctx, path=model.ProviderNode._getPath(request.nodes[0]))
        self.assertEqual(['fake key fake base64'], node.host_keys)

    @simple_layout('layouts/nodepool-image.yaml', enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @return_data(
        'build-ubuntu-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.ubuntu_return_data,
    )
    # Use an existing image id since the upload methods aren't
    # implemented in boto; the actualy upload process will be tested
    # in test_aws_driver.
    @mock.patch('zuul.driver.aws.awsendpoint.AwsProviderEndpoint.uploadImage',
                return_value="ami-1e749f67")
    def test_image_build_node_lifecycle(self, mock_uploadimage):
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)

        for _ in iterate_timeout(60, "upload to complete"):
            uploads = self.launcher.image_upload_registry.getUploadsForImage(
                'review.example.com%2Forg%2Fcommon-config/debian-local')
            self.assertEqual(1, len(uploads))
            pending = [u for u in uploads if u.external_id is None]
            if not pending:
                break

        nodeset = model.NodeSet()
        nodeset.addNode(model.Node("node", "debian-local-normal"))

        ctx = self.createZKContext(None)
        request = self.requestNodes([n.label for n in nodeset.getNodes()])

        client = LauncherClient(self.zk_client, None)
        request = client.getRequest(request.uuid)

        self.assertEqual(request.state, model.NodesetRequest.State.FULFILLED)
        self.assertEqual(len(request.nodes), 1)

        client.acceptNodeset(request, nodeset)
        self.waitUntilSettled()

        with testtools.ExpectedException(NoNodeError):
            # Request should be gone
            request.refresh(ctx)

        for node in nodeset.getNodes():
            pnode = node._provider_node
            self.assertIsNotNone(pnode)
            self.assertTrue(pnode.hasLock())

        client.useNodeset(nodeset)
        self.waitUntilSettled()

        for node in nodeset.getNodes():
            pnode = node._provider_node
            self.assertTrue(pnode.hasLock())
            self.assertTrue(pnode.state, pnode.State.IN_USE)

        client.returnNodeset(nodeset)
        self.waitUntilSettled()

        for node in nodeset.getNodes():
            pnode = node._provider_node
            self.assertFalse(pnode.hasLock())
            self.assertTrue(pnode.state, pnode.State.USED)

            for _ in iterate_timeout(60, "node to be deleted"):
                try:
                    pnode.refresh(ctx)
                except NoNodeError:
                    break

    @simple_layout('layouts/nodepool-multi-provider.yaml',
                   enable_nodepool=True)
    @driver_config('test_launcher', quotas={
        'instances': 1,
    })
    def test_relative_priority(self):
        # Test that we spread quota use out among multiple providers
        self.waitUntilSettled()

        client = LauncherClient(self.zk_client, None)
        # Create a request so the following requests can't be fulfilled
        # due to instance quota.
        request0 = self.requestNodes(["debian-normal"])
        nodes0 = self.getNodes(request0)
        self.assertEqual(1, len(nodes0))

        requests = []
        ctx = self.createZKContext(None)
        for _ in range(2):
            request = model.NodesetRequest.new(
                ctx,
                tenant_name="tenant-one",
                pipeline_name="test",
                buildset_uuid=uuid.uuid4().hex,
                job_uuid=uuid.uuid4().hex,
                job_name="foobar",
                labels=["debian-normal"],
                priority=100,
                request_time=time.time(),
                zuul_event_id=uuid.uuid4().hex,
                span_info=None,
            )
            requests.append(request)

        # Revise relative priority, so that the last requests has
        # the highest relative priority.
        request1_p2, request2_p1 = requests
        client.reviseRequest(request1_p2, relative_priority=2)
        client.reviseRequest(request2_p1, relative_priority=1)

        # Delete the initial request to free up the instance
        request0.delete(ctx)
        # Last request should be fulfilled
        for _ in iterate_timeout(10, "request to be fulfilled"):
            request2_p1.refresh(ctx)
            if request2_p1.state == request2_p1.State.FULFILLED:
                break

        # Lower priority request should not be fulfilled
        request1_p2.refresh(ctx)
        self.assertEqual(request1_p2.State.ACCEPTED, request1_p2.state)


class TestMinReadyLauncher(LauncherBaseTestCase):
    tenant_config_file = "config/launcher-min-ready/main.yaml"

    def test_min_ready(self):
        for _ in iterate_timeout(60, "nodes to be ready"):
            nodes = self.launcher.api.nodes_cache.getItems()
            # Since we are randomly picking a provider to fill the
            # min-ready slots we might end up with 3-5 nodes
            # depending on the choice of providers.
            if not 3 <= len(nodes) <= 5:
                continue
            if all(n.state == n.State.READY for n in nodes):
                break

        self.waitUntilSettled()
        nodes = self.launcher.api.nodes_cache.getItems()
        self.assertGreaterEqual(len(nodes), 3)
        self.assertLessEqual(len(nodes), 5)

        self.executor_server.hold_jobs_in_build = True
        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()
        B = self.fake_gerrit.addFakeChange('org/project2', 'master', 'B')
        B.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(B.addApproval('Approved', 1))
        self.waitUntilSettled()

        for _ in iterate_timeout(30, "nodes to be in-use"):
            # We expect the launcher to use the min-ready nodes
            in_use_nodes = [n for n in nodes if n.state == n.State.IN_USE]
            if len(in_use_nodes) == 2:
                break

        self.assertEqual(nodes[0].host_keys, [])

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        check_job_a = self.getJobFromHistory('check-job', project=A.project)
        self.assertEqual(check_job_a.result,
                         'SUCCESS')
        self.assertEqual(A.data['status'], 'MERGED')
        self.assertEqual(A.reported, 2)
        self.assertEqual(check_job_a.node,
                         'debian-normal')

        check_job_b = self.getJobFromHistory('check-job', project=A.project)
        self.assertEqual(check_job_b.result,
                         'SUCCESS')
        self.assertEqual(A.data['status'], 'MERGED')
        self.assertEqual(A.reported, 2)
        self.assertEqual(check_job_b.node,
                         'debian-normal')

        # Wait for min-ready slots to be refilled
        for _ in iterate_timeout(60, "nodes to be ready"):
            nodes = self.launcher.api.nodes_cache.getItems()
            if not 3 <= len(nodes) <= 5:
                continue
            if all(n.state == n.State.READY for n in nodes):
                break

        self.waitUntilSettled()
        nodes = self.launcher.api.nodes_cache.getItems()
        self.assertGreaterEqual(len(nodes), 3)
        self.assertLessEqual(len(nodes), 5)

    def test_max_ready_age(self):
        for _ in iterate_timeout(60, "nodes to be ready"):
            nodes = self.launcher.api.nodes_cache.getItems()
            # Since we are randomly picking a provider to fill the
            # min-ready slots we might end up with 3-5 nodes
            # depending on the choice of providers.
            if not 3 <= len(nodes) <= 5:
                continue
            if all(n.state == n.State.READY for n in nodes):
                break

        self.waitUntilSettled()
        nodes = self.launcher.api.nodes_cache.getItems()
        self.assertGreaterEqual(len(nodes), 3)
        self.assertLessEqual(len(nodes), 5)

        nodes_by_label = self._nodes_by_label()
        self.assertEqual(1, len(nodes_by_label['debian-emea']))
        node = nodes_by_label['debian-emea'][0]

        ctx = self.createZKContext(None)
        try:
            node.acquireLock(ctx)
            node.updateAttributes(ctx, state_time=0)
        finally:
            node.releaseLock(ctx)

        for _ in iterate_timeout(60, "node to be cleaned up"):
            nodes = self.launcher.api.nodes_cache.getItems()
            if node in nodes:
                continue
            if not 3 <= len(nodes) <= 5:
                continue
            if all(n.state == n.State.READY for n in nodes):
                break

        self.waitUntilSettled()
        nodes_by_label = self._nodes_by_label()
        self.assertEqual(1, len(nodes_by_label['debian-emea']))


class TestMinReadyTenantVariant(LauncherBaseTestCase):
    tenant_config_file = "config/launcher-min-ready/tenant-variant.yaml"

    def test_min_ready(self):
        # tenant-one:
        #   common-config:
        #     Provider aws-us-east-1-main
        #       debian-normal (t3.medium)  (hash A)
        #   project1:
        #     Provider aws-eu-central-1-main
        #       debian-emea
        #     Provider aws-ca-central-1-main
        #       debian-normal (t3.small)   (hash B)
        # tenant-two:
        #   common-config:
        #     Provider aws-us-east-1-main
        #       debian-normal (t3.medium)  (hash C)
        #   project2:
        #     Image debian (for tenant 2)

        # min-ready=2 for debian-normal
        #   2 from aws-us-east-1-main
        #   2 from aws-ca-central-1-main
        # min-ready=1 for debian-emea
        #   1 from aws-eu-central-1-main
        for _ in iterate_timeout(60, "nodes to be ready"):
            nodes = self.launcher.api.nodes_cache.getItems()
            if len(nodes) != 5:
                continue
            if all(n.state == n.State.READY for n in nodes):
                break

        self.waitUntilSettled()
        nodes = self.launcher.api.nodes_cache.getItems()
        self.assertEqual(5, len(nodes))

        nodes_by_label = self._nodes_by_label()
        self.assertEqual(4, len(nodes_by_label['debian-normal']))
        debian_normal_cfg_hashes = {
            n.label_config_hash for n in nodes_by_label['debian-normal']
        }
        # We will get 2 nodes with hash C, and then 2 nodes with hash
        # A or B, so that's 2 or 3 hashes.
        self.assertGreaterEqual(len(debian_normal_cfg_hashes), 2)
        self.assertLessEqual(len(debian_normal_cfg_hashes), 3)

        files = {
            'zuul-extra.d/image.yaml': textwrap.dedent(
                '''
                - image:
                    name: debian
                    type: cloud
                    description: "Debian test image"
                '''
            )
        }
        self.addCommitToRepo('org/project1', 'Change label config', files)
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()

        for _ in iterate_timeout(60, "nodes to be ready"):
            nodes = self.launcher.api.nodes_cache.getItems()
            if len(nodes) != 5:
                continue
            if all(n.state == n.State.READY for n in nodes):
                break

        nodes = self.launcher.api.nodes_cache.getItems()
        self.assertEqual(5, len(nodes))

        nodes_by_label = self._nodes_by_label()
        self.assertEqual(1, len(nodes_by_label['debian-emea']))
        self.assertEqual(4, len(nodes_by_label['debian-normal']))
        debian_normal_cfg_hashes = {
            n.label_config_hash for n in nodes_by_label['debian-normal']
        }
        self.assertGreaterEqual(len(debian_normal_cfg_hashes), 2)
        self.assertLessEqual(len(debian_normal_cfg_hashes), 3)


class TestNodesetRequestPriority(LauncherBaseTestCase):
    config_file = 'zuul.conf'
    tenant_config_file = 'config/single-tenant/main-launcher.yaml'

    def test_pipeline_priority(self):
        "Test that nodes are requested at the correct pipeline priority"
        self.hold_nodeset_requests_in_queue = True

        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.setMerged()
        self.fake_gerrit.addEvent(A.getRefUpdatedEvent())
        self.waitUntilSettled()

        B = self.fake_gerrit.addFakeChange('org/project1', 'master', 'B')
        self.fake_gerrit.addEvent(B.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        C = self.fake_gerrit.addFakeChange('org/project', 'master', 'C')
        C.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(C.addApproval('Approved', 1))
        self.waitUntilSettled()

        reqs = self.launcher.api.getNodesetRequests()

        # The requests come back sorted by priority. Since we have
        # three requests for the three changes each with a different
        # priority.

        # * gate first - high priority - change C
        self.assertEqual(reqs[0].priority, 100)
        self.assertEqual(reqs[0].labels, ['label1'])
        # * check second - normal priority - change B
        self.assertEqual(reqs[1].priority, 200)
        self.assertEqual(reqs[1].labels, ['label1'])
        # * post third - low priority - change A
        # additionally, the post job defined uses an ubuntu-xenial node,
        # so we include that check just as an extra verification
        self.assertEqual(reqs[2].priority, 300)
        self.assertEqual(reqs[2].labels, ['ubuntu-xenial'])

        self.hold_nodeset_requests_in_queue = False
        self.releaseNodesetRequests(*reqs)

        self.waitUntilSettled()
        self.assertHistory([
            dict(name='project-merge', result='SUCCESS', changes='2,1'),
            dict(name='project-test1', result='SUCCESS', changes='2,1'),
            dict(name='project-test2', result='SUCCESS', changes='2,1'),
            dict(name='project-merge', result='SUCCESS', changes='3,1'),
            dict(name='project-test1', result='SUCCESS', changes='3,1'),
            dict(name='project-test2', result='SUCCESS', changes='3,1'),
            dict(name='project1-project2-integration',
                 result='SUCCESS', changes='2,1'),
            dict(name='project-post', result='SUCCESS'),
        ], ordered=False)

    @simple_layout('layouts/two-projects-integrated.yaml',
                   enable_nodepool=True)
    def test_relative_priority_check(self):
        "Test that nodes are requested at the relative priority"
        self.hold_nodeset_requests_in_queue = True

        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B')
        self.fake_gerrit.addEvent(B.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        C = self.fake_gerrit.addFakeChange('org/project1', 'master', 'C')
        self.fake_gerrit.addEvent(C.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        D = self.fake_gerrit.addFakeChange('org/project2', 'master', 'D')
        self.fake_gerrit.addEvent(D.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        # The requests come back sorted by priority.
        reqs = self.launcher.api.getNodesetRequests()

        # Change A, first change for project, high relative priority.
        self.assertEqual(reqs[0].priority, 200)
        self.assertEqual(reqs[0].relative_priority, 0)

        # Change C, first change for project1, high relative priority.
        self.assertEqual(reqs[1].priority, 200)
        self.assertEqual(reqs[1].relative_priority, 0)

        # Change B, second change for project, lower relative priority.
        self.assertEqual(reqs[2].priority, 200)
        self.assertEqual(reqs[2].relative_priority, 1)

        # Change D, first change for project2 shared with project1,
        # lower relative priority than project1.
        self.assertEqual(reqs[3].priority, 200)
        self.assertEqual(reqs[3].relative_priority, 1)

        # Fulfill only the first request
        ctx = self.createZKContext(None)
        reqs[0].updateAttributes(ctx, state=reqs[0].State.REQUESTED)
        for x in iterate_timeout(30, 'fulfill request'):
            reqs = self.launcher.api.getNodesetRequests()
            if len(reqs) < 4:
                break
        self.waitUntilSettled()

        reqs = self.launcher.api.getNodesetRequests()

        # Change B, now first change for project, equal priority.
        self.assertEqual(reqs[0].priority, 200)
        self.assertEqual(reqs[0].relative_priority, 0)

        # Change C, now first change for project1, equal priority.
        self.assertEqual(reqs[1].priority, 200)
        self.assertEqual(reqs[1].relative_priority, 0)

        # Change D, first change for project2 shared with project1,
        # still lower relative priority than project1.
        self.assertEqual(reqs[2].priority, 200)
        self.assertEqual(reqs[2].relative_priority, 1)

        self.hold_nodeset_requests_in_queue = False
        self.releaseNodesetRequests(*reqs)
        self.waitUntilSettled()

    @simple_layout('layouts/two-projects-integrated.yaml',
                   enable_nodepool=True)
    def test_relative_priority_long(self):
        "Test that nodes are requested at the relative priority"
        self.hold_nodeset_requests_in_queue = True

        count = 13
        changes = []
        for x in range(count):
            change = self.fake_gerrit.addFakeChange(
                'org/project', 'master', 'A')
            self.fake_gerrit.addEvent(change.getPatchsetCreatedEvent(1))
            self.waitUntilSettled()
            changes.append(change)

        reqs = self.launcher.api.getNodesetRequests()
        self.assertEqual(len(reqs), 13)
        # The requests come back sorted by priority.
        for x in range(10):
            self.assertEqual(reqs[x].relative_priority, x)
        self.assertEqual(reqs[10].relative_priority, 10)
        self.assertEqual(reqs[11].relative_priority, 10)
        self.assertEqual(reqs[12].relative_priority, 10)

        # Fulfill only the first request
        self.releaseNodesetRequests(reqs[0])
        self.waitUntilSettled()

        reqs = self.launcher.api.getNodesetRequests()
        self.assertEqual(len(reqs), 12)
        for x in range(10):
            self.assertEqual(reqs[x].relative_priority, x)
        self.assertEqual(reqs[10].relative_priority, 10)
        self.assertEqual(reqs[11].relative_priority, 10)

        self.hold_nodeset_requests_in_queue = False
        self.releaseNodesetRequests(*reqs)
        self.waitUntilSettled()

    @simple_layout('layouts/two-projects-integrated.yaml',
                   enable_nodepool=True)
    def test_relative_priority_gate(self):
        "Test that nodes are requested at the relative priority"
        self.hold_nodeset_requests_in_queue = True

        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        B = self.fake_gerrit.addFakeChange('org/project2', 'master', 'B')
        B.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(B.addApproval('Approved', 1))
        self.waitUntilSettled()

        # project does not share a queue with project1 and project2.
        C = self.fake_gerrit.addFakeChange('org/project', 'master', 'C')
        C.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(C.addApproval('Approved', 1))
        self.waitUntilSettled()

        # The requests come back sorted by priority.
        reqs = self.launcher.api.getNodesetRequests()

        # Change A, first change for shared queue, high relative
        # priority.
        self.assertEqual(reqs[0].priority, 100)
        self.assertEqual(reqs[0].relative_priority, 0)

        # Change C, first change for independent project, high
        # relative priority.
        self.assertEqual(reqs[1].priority, 100)
        self.assertEqual(reqs[1].relative_priority, 0)

        # Change B, second change for shared queue, lower relative
        # priority.
        self.assertEqual(reqs[2].priority, 100)
        self.assertEqual(reqs[2].relative_priority, 1)

        self.hold_nodeset_requests_in_queue = False
        self.releaseNodesetRequests(*reqs)
        self.waitUntilSettled()


class TestExecutorZone(LauncherBaseTestCase):
    tenant_config_file = 'config/single-tenant/main.yaml'

    def setup_config(self, config_file: str):
        config = super().setup_config(config_file)
        config.set('executor', 'zone', 'us-east-1')
        return config

    @simple_layout('layouts/nodepool-executor-zone.yaml', enable_nodepool=True)
    def test_jobs_executed(self):
        self.hold_jobs_in_queue = True
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        queue = list(self.executor_api.queued())
        self.assertEqual(len(self.builds), 0)
        self.assertEqual(len(queue), 1)
        self.assertEqual('us-east-1', queue[0].zone)

        self.hold_jobs_in_queue = False
        self.executor_api.release()
        self.waitUntilSettled()

        self.assertEqual(self.getJobFromHistory('check-job').result,
                         'SUCCESS')
        self.assertEqual(A.data['status'], 'MERGED')
        self.assertEqual(A.reported, 2)
        self.assertEqual(self.getJobFromHistory('check-job').node,
                         'debian-normal')
