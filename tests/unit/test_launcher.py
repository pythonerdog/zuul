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
import re
import textwrap
import threading
import time
import uuid
from collections import defaultdict
from unittest import mock

from zuul import exceptions
from zuul import model
import zuul.driver.aws.awsendpoint
from zuul.launcher.client import LauncherClient
import zuul.launcher.server

import cachetools
import fixtures
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
    raw_body = 'test raw image'
    raw_sha256 = ('d043e8080c82dbfeca3199a24d5f019'
                  '3e66755b5ba62d6b60107a248996a6795')
    raw_md5sum = '78d2d3ff2463bc75c7cc1d38b8df6a6b'
    zst_body = b'(\xb5/\xfd\x04Xq\x00\x00test raw image\xc4\xcf\x97b'
    qcow2_body = 'test qcow2 image' * 4096
    qcow2_sha256 = ('6d30f48ee68786c12c7a6915dad1a7bd8'
                    '24b85a13c629583465de97bfb3f5b51')
    qcow2_md5sum = 'a2e23f2a097ac05d85dfebf44841869c'

    def __init__(self):
        super().__init__()
        self.requests_mock.add_passthru("http://localhost")
        self.requests_mock.add(
            responses.GET,
            'http://example.com/image.raw',
            body=self.raw_body)
        self.requests_mock.add(
            responses.GET,
            'http://example.com/image.raw.zst',
            body=self.zst_body)
        self.requests_mock.add(
            responses.GET,
            'http://example.com/image.qcow2',
            body=self.qcow2_body)
        self.requests_mock.add(
            responses.HEAD,
            'http://example.com/image.raw',
            headers={'content-length': str(len(self.raw_body))})
        self.requests_mock.add(
            responses.HEAD,
            'http://example.com/image.raw.zst',
            headers={'content-length': str(len(self.zst_body))})
        self.requests_mock.add(
            responses.HEAD,
            'http://example.com/image.qcow2',
            headers={'content-length': str(len(self.qcow2_body))})
        # The next three are for the signed_url test
        # Partial response
        self.requests_mock.add(
            responses.GET,
            'http://example.com/getonly.raw',
            match=[responses.matchers.header_matcher({"Range": "bytes=0-0"})],
            status=206,
            headers={'content-length': '1',
                     'content-range': f'bytes 0-0/{len(self.raw_body)}'},
        )
        # The full response
        self.requests_mock.add(
            responses.GET,
            'http://example.com/getonly.raw',
            headers={'content-length': str(len(self.raw_body))},
            body=self.raw_body)
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
                        'sha256': ImageMocksFixture.raw_sha256,
                        'md5sum': ImageMocksFixture.raw_md5sum,
                    }
                }, {
                    'name': 'qcow2 image',
                    'url': 'http://example.com/image.qcow2',
                    'metadata': {
                        'type': 'zuul_image',
                        'image_name': 'debian-local',
                        'format': 'qcow2',
                        'sha256': ImageMocksFixture.qcow2_sha256,
                        'md5sum': ImageMocksFixture.qcow2_md5sum,
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
                        'sha256': ImageMocksFixture.raw_sha256,
                        'md5sum': ImageMocksFixture.raw_md5sum,
                    }
                }, {
                    'name': 'qcow2 image',
                    'url': 'http://example.com/image.qcow2',
                    'metadata': {
                        'type': 'zuul_image',
                        'image_name': 'ubuntu-local',
                        'format': 'qcow2',
                        'sha256': ImageMocksFixture.qcow2_sha256,
                        'md5sum': ImageMocksFixture.qcow2_md5sum,
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

    def _waitForUploads(self, image_cname, count=None):
        for _ in iterate_timeout(60, "upload to complete"):
            uploads = self.launcher.image_upload_registry.getUploadsForImage(
                image_cname)
            pending = [u for u in uploads if u.external_id is None]
            if not pending:
                if count is None or count == len(uploads):
                    return uploads

    def _waitForLauncherLayoutSync(self, tenant='tenant-one'):
        for _ in iterate_timeout(
                30, "scheduler and launcher to have the same layout"):
            if (self.scheds.first.sched.local_layout_state.get(tenant) ==
                self.launcher.local_layout_state.get(tenant)):
                break

    def _waitForNoChildren(self, path):
        for _ in iterate_timeout(10, f"empty path {path}"):
            znodes = self.zk_client.client.get_children('/zuul/nodeset/locks')
            if not len(znodes):
                return

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
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="test_external_id")
    def test_launcher_missing_image_build(self, mock_image_upload_run):
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

        build = self.getJobFromHistory('build-debian-local-image')
        formats = build.parameters['zuul']['image_formats']
        self.assertEqual(['raw'], formats)
        self.assertEqual(
            'debian-local', build.parameters['zuul']['image_build_name'])

        build = self.getJobFromHistory('build-ubuntu-local-image')
        formats = build.parameters['zuul']['image_formats']
        self.assertEqual(['raw'], formats)
        self.assertEqual(
            'ubuntu-local', build.parameters['zuul']['image_build_name'])

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
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="test_external_id")
    def test_launcher_image_expire(self, mock_image_upload_run):
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
        artifacts1 = self._waitForArtifacts(image_cname, 1)
        artifacts1_uuids = set([x.uuid for x in artifacts1])

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
        artifacts2 = self._waitForArtifacts(image_cname, 2)
        artifacts2_uuids = set([x.uuid for x in artifacts2])
        self.assertTrue(artifacts1_uuids < artifacts2_uuids)

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
        artifacts3 = self._waitForArtifacts(image_cname, 2)
        artifacts3_uuids = set([x.uuid for x in artifacts3])
        self.assertFalse(artifacts3_uuids.isdisjoint(artifacts2_uuids))
        self.assertTrue(artifacts3_uuids.isdisjoint(artifacts1_uuids))

    @simple_layout('layouts/nodepool-image-no-validate.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
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
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="ami-785db401")
    def test_launcher_image_validation(self, mock_image_upload_run):
        # Test a two-stage image-build where we do run the validate
        # stage.
        self.executor_server.hold_jobs_in_build = True
        self.waitUntilSettled()

        self.executor_server.release('build-debian-local-image')
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
        ])

        nodes = self.launcher.api.getProviderNodes()
        self.assertEqual(len(nodes), 2)
        for node in nodes:
            self.assertEqual(node.create_state['image_external_id'],
                             mock_image_upload_run.return_value)

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='validate-debian-local-image', result='SUCCESS'),
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
            dict(name='validate-debian-local-image', result='SUCCESS'),
        ])

        name = 'review.example.com%2Forg%2Fcommon-config/debian-local'
        artifact = self._waitForArtifacts(name, 1)[0]
        self.assertEqual('raw', artifact.format)
        self.assertFalse(artifact.validated)
        uploads = self.launcher.image_upload_registry.getUploadsForImage(
            name)
        self.assertEqual(2, len(uploads))
        for upload in uploads:
            self.assertEqual(artifact.uuid, upload.artifact_uuid)
            self.assertEqual(mock_image_upload_run.return_value,
                             upload.external_id)
            self.assertTrue(upload.validated)

    @simple_layout('layouts/nodepool-image-validate.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="ami-785db401")
    def test_launcher_image_validation_failure(self, mock_image_upload_run):
        # Test a two-stage image-build where the validate stage fails.
        self.executor_server.hold_jobs_in_build = True
        self.waitUntilSettled()

        self.executor_server.release('build-debian-local-image')
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
        ])

        nodes = self.launcher.api.getProviderNodes()
        self.assertEqual(len(nodes), 2)
        for node in nodes:
            self.assertEqual(node.create_state['image_external_id'],
                             mock_image_upload_run.return_value)

        self.assertEqual(len(self.builds), 2)
        for build in self.builds:
            build.should_fail = True

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='validate-debian-local-image', result='FAILURE'),
            dict(name='validate-debian-local-image', result='FAILURE'),
        ])

        name = 'review.example.com%2Forg%2Fcommon-config/debian-local'
        artifact = self._waitForArtifacts(name, 1)[0]
        self.assertEqual('raw', artifact.format)
        self.assertFalse(artifact.validated)
        uploads = self.launcher.image_upload_registry.getUploadsForImage(
            name)
        self.assertEqual(2, len(uploads))
        for upload in uploads:
            self.assertEqual(artifact.uuid, upload.artifact_uuid)
            self.assertFalse(upload.validated)

    @simple_layout('layouts/nodepool-image.yaml', enable_nodepool=True)
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="test_external_id")
    def test_launcher_crashed_upload(self, mock_image_upload_run):
        self.waitUntilSettled()
        provider = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-main')
        endpoint = provider.getEndpoint()
        image = list(provider.images.values())[1]
        self.assertEqual('debian-local', image.name)
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
                md5sum=ImageMocksFixture.raw_md5sum,
                sha256=ImageMocksFixture.raw_sha256,
                timestamp=time.time(),
            )
            with iba.locked(ctx):
                model.ImageUpload.new(
                    ctx,
                    uuid='upload-uuid',
                    artifact_uuid='iba-uuid',
                    endpoint_name=endpoint.canonical_name,
                    providers=[provider.canonical_name],
                    canonical_name=image.canonical_name,
                    config_hash=image.config_hash,
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

    @simple_layout('layouts/nodepool-image.yaml', enable_nodepool=True)
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                side_effect="test_external_id")
    def test_launcher_no_multiple_uploads(self, mock_image_upload_run):
        # Make sure that we don't enqueue multiple upload jobs for the
        # same pending uploads
        self.waitUntilSettled()
        provider = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-main')
        endpoint = provider.getEndpoint()
        image = list(provider.images.values())[1]
        self.assertEqual('debian-local', image.name)

        upload_event = threading.Event()
        upload_counter = 0
        orig_upload_run = zuul.launcher.server.UploadJob.run

        def fake_upload_run(*args, **kw):
            nonlocal upload_counter
            upload_counter += 1
            upload_event.wait()
            return orig_upload_run(*args, **kw)

        self.useFixture(fixtures.MonkeyPatch(
            'zuul.launcher.server.UploadJob.run',
            fake_upload_run))

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
                md5sum=ImageMocksFixture.raw_md5sum,
                sha256=ImageMocksFixture.raw_sha256,
                timestamp=time.time(),
            )
            with iba.locked(ctx):
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
        with self.launcher._test_lock:
            self.launcher.checkMissingUploads()
            self.launcher.checkMissingUploads()
        upload_event.set()
        self.waitUntilSettled()
        self.assertEqual(1, upload_counter)

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
                        'sha256': ImageMocksFixture.raw_sha256,
                        'md5sum': ImageMocksFixture.raw_md5sum,
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
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="test_external_id")
    def test_launcher_image_signed_url(self, mock_image_upload_run):
        # If the image is uploaded using a signed url, it will not
        # permit a HEAD request; this tests the GET range fallback.

        self.waitUntilSettled()
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

    @simple_layout('layouts/nodepool-image.yaml', enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        getonly_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="test_external_id")
    def test_launcher_image_cleanup(self, mock_image_upload_run):
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
            dict(name='build-ubuntu-local-image', result='SUCCESS'),
        ], ordered=False)

        # Clear out Zuul config to remove the provider, which
        # has the same effect as a provider config error.
        files = {'zuul.yaml': ""}
        self.addCommitToRepo(
            'org/common-config', 'Change label config', files)

        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()

        def _assert_image_state():
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

        self.launcher.checkOldImages()
        _assert_image_state()

        self.commitConfigUpdate(
            "org/common-config", 'layouts/nodepool-image.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()

        self.launcher.checkOldImages()
        _assert_image_state()

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_jobs_executed(self):
        self.executor_server.hold_jobs_in_build = True

        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        nodes = self.launcher.api.nodes_cache.getItems()
        self.assertEqual(nodes[0].host_keys, [])
        provider = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-main')
        used = self.launcher.getUnmanagedQuotaUsed(provider)
        self.assertEqual(0, used.getResources().get('instances', 0))
        self.launcher._runStats()

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
            f'zuul.provider.{pname}.nodes.state.in-use',
            kind='g')
        self.assertReportedStat(
            f'zuul.provider.{pname}.label.debian-normal.nodes.state.in-use',
            kind='g')
        self.assertReportedStat(
            'zuul.nodes.state.in-use',
            kind='g')
        for _ in iterate_timeout(60, "nodes to be deleted"):
            if len(self.launcher.api.nodes_cache.getItems()) == 0:
                break
        self._waitForNoChildren('/zuul/nodeset/locks')
        self._waitForNoChildren('/zuul/nodeset/requests')
        self._waitForNoChildren('/zuul/nodes/locks')
        self._waitForNoChildren('/zuul/nodes/nodes')

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
        self._waitForNoChildren('/zuul/nodeset/locks')
        self._waitForNoChildren('/zuul/nodeset/requests')

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

    @simple_layout('layouts/launch-timeout.yaml', enable_nodepool=True)
    def test_launcher_launch_timeout(self):
        with mock.patch(
            'zuul.driver.aws.awsendpoint.AwsProviderEndpoint._refresh'
        ) as refresh_mock:
            # Patch 'endpoint._refresh()' to return w/o updating
            refresh_mock.side_effect = lambda o: o

            request = self.requestNodes(['debian-normal'])
            self.assertEqual(request.state, model.NodesetRequest.State.FAILED)

    @simple_layout('layouts/nodepool-untrusted-conf.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="test_external_id")
    def test_launcher_untrusted_project(self, mock_image_upload_run):
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
    @mock.patch('zuul.launcher.server.Launcher.doesProviderHaveQuotaForLabel',
                return_value=True)
    @mock.patch('zuul.driver.aws.awsprovider.AwsProvider.getQuotaForLabel',
                return_value=model.QuotaInformation())
    def test_failed_node(self, mock_quota, mock_quota2):
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
        with self.launcher._run_lock:
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
        'instances': 2,
    })
    def test_preferred_provider(self):
        # Test that we supply nodes from the requested provider if possible
        self.waitUntilSettled()

        request1 = self.requestNodes(["debian-normal"])
        nodes1 = self.getNodes(request1)
        self.assertEqual(1, len(nodes1))

        # Normally we would expect a second node to come from the
        # other provider (the test above this verifies that), but
        # let's specifically request the same provider.
        request2 = self.requestNodes(
            ["debian-normal"], provider=nodes1[0].provider)
        nodes2 = self.getNodes(request2)
        self.assertEqual(1, len(nodes2))

        self.assertEqual(nodes1[0].provider, nodes2[0].provider)

    @simple_layout('layouts/nodepool.yaml',
                   enable_nodepool=True)
    @driver_config('test_launcher', quotas={
        'instances': 2,
    })
    def test_quota_external_usage(self):
        # Test that we spread quota use out among multiple providers
        self.waitUntilSettled()

        # Create 2 unmanaged instances that eat up our quota
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        ec2_client.run_instances(
            ImageId="ami-12c6146b", MinCount=2, MaxCount=2,
        )
        self.launcher._provider_quota_cache.clear()

        # We expect a timeout waiting for nodes, and no other exceptions
        with testtools.ExpectedException(Exception):
            self.requestNodes(["debian-normal"])

    @simple_layout('layouts/nodepool.yaml',
                   enable_nodepool=True)
    @driver_config('test_launcher', quotas={
        'instances': 0,
    })
    def test_quota_insufficient_capacity(self):
        # Test that we fail requests which are impossible to satisfy
        self.waitUntilSettled()
        request = self.requestNodes(["debian-normal"])
        self.assertEqual(request.state, model.NodesetRequest.State.FAILED)

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
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
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

    @simple_layout('layouts/launcher-image-lifecycle/phase1.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        LauncherBaseTestCase.debian_return_data,
    )
    @mock.patch('zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
                return_value="ami-1e749f67")
    def test_image_delete_lifecycle(self, mock_uploadimage):
        self.waitUntilSettled("phase1")
        # Initialize some values for later

        class FakeNode:
            pass

        node = FakeNode
        node.image_upload_uuid = None
        node.label = 'debian-local-normal'
        image_cname = 'review.example.com%2Forg%2Fcommon-config/debian-local'
        image_id = "ami-1e749f67"

        self.assertHistory([
            dict(name='build-debian-local-image', result='SUCCESS'),
        ], ordered=False)
        uploads = self._waitForUploads(image_cname)
        # At this point the image should be in one provider only
        self.assertEqual(1, len(uploads))
        provider_main = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-main')
        self.assertEqual(
            image_id, self.launcher.getImageExternalId(node, provider_main))

        # Add the image to the other providers
        self.commitConfigUpdate(
            'org/common-config',
            'layouts/launcher-image-lifecycle/phase2.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self._waitForLauncherLayoutSync()

        self.waitUntilSettled("phase2")
        uploads = self._waitForUploads(image_cname)
        self.assertEqual(1, len(uploads))
        provider_main = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-main')
        provider_same = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-same')
        provider_diff = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-different')
        self.assertEqual(
            image_id, self.launcher.getImageExternalId(node, provider_main))
        self.assertEqual(
            image_id, self.launcher.getImageExternalId(node, provider_same))
        with testtools.ExpectedException(Exception, "No image found"):
            self.assertEqual(
                image_id, self.launcher.getImageExternalId(
                    node, provider_diff))

        # Update the config for the main provider
        self.commitConfigUpdate(
            'org/common-config',
            'layouts/launcher-image-lifecycle/phase3.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self._waitForLauncherLayoutSync()

        self.waitUntilSettled("phase3")
        uploads = self._waitForUploads(image_cname)
        self.assertEqual(1, len(uploads))
        provider_main = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-main')
        provider_same = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-same')
        provider_diff = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-different')
        self.assertEqual(
            image_id, self.launcher.getImageExternalId(node, provider_main))
        self.assertEqual(
            image_id, self.launcher.getImageExternalId(node, provider_same))
        with testtools.ExpectedException(Exception, "No image found"):
            self.assertEqual(
                image_id, self.launcher.getImageExternalId(
                    node, provider_diff))

        # Remove the image from the other providers
        self.commitConfigUpdate(
            'org/common-config',
            'layouts/launcher-image-lifecycle/phase4.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self._waitForLauncherLayoutSync()

        self.waitUntilSettled("phase4")
        uploads = self._waitForUploads(image_cname)
        self.assertEqual(1, len(uploads))
        provider_main = self.launcher._getProvider(
            'tenant-one', 'aws-us-east-1-main')
        self.assertEqual(
            image_id, self.launcher.getImageExternalId(node, provider_main))

        # Remove the image from all providers
        self.commitConfigUpdate(
            'org/common-config',
            'layouts/launcher-image-lifecycle/phase5.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self._waitForLauncherLayoutSync()

        self.waitUntilSettled("phase5")
        uploads = self._waitForUploads(image_cname, count=0)

    @simple_layout('layouts/nodepool.yaml',
                   enable_nodepool=True)
    @driver_config('test_launcher', quotas={
        'instances': 1,
    })
    def test_relative_priority(self):
        self.waitUntilSettled()

        client = LauncherClient(self.zk_client, None)
        # Create a request so the following requests can't be fulfilled
        # due to instance quota.
        request0 = self.requestNodes(["debian-normal"])
        nodes0 = self.getNodes(request0)
        self.assertEqual(1, len(nodes0))

        # Make sure the next requests always have current quota info
        self.launcher._provider_quota_cache = cachetools.TTLCache(
            maxsize=8192, ttl=0)
        self.launcher._provider_available_cache = cachetools.TTLCache(
            maxsize=8192, ttl=0)

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

        # Allow the main loop to run to verify that we defer the
        # requests
        time.sleep(2)
        # Revise relative priority, so that the last requests has
        # the highest relative priority.
        with self.launcher._run_lock:
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
        self.assertEqual(request1_p2.State.REQUESTED, request1_p2.state)

    @simple_layout('layouts/launcher-noop.yaml',
                   enable_nodepool=True)
    @okay_tracebacks('_getQuotaForInstanceType')
    def test_noop_job(self):
        # Test that nodeset fallback works
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        self.assertEqual(A.data['status'], 'NEW')
        self.assertEqual(A.reported, 1)
        self.assertIn('Build succeeded', A.messages[0])
        self.assertHistory([])
        ids = self.scheds.first.sched.launcher.getRequestIds()
        self.assertEqual(0, len(ids))

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_autohold(self):
        self.scheds.first.sched.autohold(
            'tenant-one', 'review.example.com/org/project', 'check-job',
            ".*", "reason text", 1, None)

        # There should be a record in ZooKeeper
        request_list = self.sched_zk_nodepool.getHoldRequests()
        self.assertEqual(1, len(request_list))
        request = self.sched_zk_nodepool.getHoldRequest(
            request_list[0])
        self.assertIsNotNone(request)
        self.assertEqual('tenant-one', request.tenant)
        self.assertEqual('review.example.com/org/project', request.project)
        self.assertEqual('check-job', request.job)
        self.assertEqual('reason text', request.reason)
        self.assertEqual(1, request.max_count)
        self.assertEqual(0, request.current_count)
        self.assertEqual([], request.nodes)

        # First check that successful jobs do not autohold
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))

        self.waitUntilSettled()

        self.assertEqual(A.data['status'], 'NEW')
        self.assertEqual(A.reported, 1)
        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1'),
        ], ordered=False)

        # Check for a held node
        held_node = None
        self.launcher.api.nodes_cache.waitForSync()
        for node in self.launcher.api.nodes_cache.getItems():
            if node.state == node.State.HOLD:
                held_node = node
                break
        self.assertIsNone(held_node)

        # Hold in build to check the stats
        self.executor_server.hold_jobs_in_build = True

        # Now test that failed jobs are autoheld

        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B')
        self.executor_server.failJob('check-job', B)
        self.fake_gerrit.addEvent(B.getPatchsetCreatedEvent(1))

        self.waitUntilSettled()

        # Get the build request object
        build = list(self.getCurrentBuilds())[0]

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual(B.data['status'], 'NEW')
        self.assertEqual(B.reported, 1)

        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1'),
            dict(name='check-job', result='FAILURE', changes='2,1'),
        ], ordered=False)
        self.assertTrue(build.held)

        # Check for a held node
        held_node = None
        self.launcher.api.nodes_cache.waitForSync()
        for node in self.launcher.api.nodes_cache.getItems():
            if node.state == node.State.HOLD:
                held_node = node
                break
        self.assertIsNotNone(held_node)
        self.assertEqual(held_node.comment, "reason text")

        # The hold request current_count should have incremented
        # and we should have recorded the held node ID.
        request2 = self.sched_zk_nodepool.getHoldRequest(
            request.id)
        self.assertEqual(request.current_count + 1, request2.current_count)
        self.assertEqual(1, len(request2.nodes))
        self.assertEqual(1, len(request2.nodes[0]["nodes"]))

        # Another failed change should not hold any more nodes
        C = self.fake_gerrit.addFakeChange('org/project', 'master', 'C')
        self.executor_server.failJob('check-job', C)
        self.fake_gerrit.addEvent(C.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()
        self.assertEqual(C.data['status'], 'NEW')
        self.assertEqual(C.reported, 1)
        self.assertHistory([
            dict(name='check-job', result='SUCCESS', changes='1,1'),
            dict(name='check-job', result='FAILURE', changes='2,1'),
            dict(name='check-job', result='FAILURE', changes='3,1'),
        ], ordered=False)

        held_nodes = 0
        self.launcher.api.nodes_cache.waitForSync()
        for node in self.launcher.api.nodes_cache.getItems():
            if node.state == node.State.HOLD:
                held_nodes += 1
        self.assertEqual(held_nodes, 1)

        # request current_count should not have changed
        request3 = self.sched_zk_nodepool.getHoldRequest(
            request2.id)
        self.assertEqual(request2.current_count, request3.current_count)

        # Deleting hold request should set held nodes to used
        client = LauncherClient(self.zk_client, None)
        self.sched_zk_nodepool.deleteHoldRequest(request3, client)

        held_nodes = 0
        self.launcher.api.nodes_cache.waitForSync()
        for node in self.launcher.api.nodes_cache.getItems():
            if node.state == node.State.HOLD:
                held_nodes += 1
        self.assertEqual(held_nodes, 0)

        for _ in iterate_timeout(60, "node to be deleted"):
            if len(self.launcher.api.nodes_cache.getItems()) == 0:
                break


class TestLauncherLocality(LauncherBaseTestCase):
    # We use a multi-tenant config here to make sure we don't end up
    # using provider objects from different tenants during provider
    # selection.
    tenant_config_file = "config/launcher-multi-tenant/main.yaml"

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
        self.assertEqual('review.example.com%2Fcommon-config/'
                         'aws-us-west-1-main', nodes2[0].provider)
        self.assertEqual('review.example.com%2Fcommon-config/'
                         'aws-us-east-1-main', nodes2[1].provider)

    @driver_config('test_launcher', quotas={
        'instances': 2,
    })
    @okay_tracebacks('_checkNodescanRequest')
    def test_provider_selection_locality_failure(self):
        # Test that we use the same provider for multiple nodes within
        # a request if possible.
        self.waitUntilSettled()

        orig_advance = zuul.launcher.server.NodescanRequest.advance
        failed_count = 0

        def my_advance(*args, **kw):
            nonlocal failed_count
            if failed_count > 0:
                return orig_advance(*args, **kw)
            failed_count += 1
            raise Exception("Test exception")

        with mock.patch.object(
            zuul.launcher.server.NodescanRequest, 'advance', my_advance
        ):
            request1 = self.requestNodes(["debian-normal", "debian-normal"],
                                         tenant="tenant-two",
                                         timeout=30)
        nodes1 = self.getNodes(request1)
        nodes1 = [n for n in nodes1 if n.state == n.State.READY]
        self.assertEqual(2, len(nodes1))

        # These can be served from either provider; both should be
        # assigned to the same one.
        self.assertEqual(nodes1[0].provider, nodes1[1].provider)

        # Ensure that we didn't leave an extra ready node
        self.assertEqual(2, len(self.launcher.api.nodes_cache.getItems()))

    @okay_tracebacks('_checkNodescanRequest')
    def test_provider_selection_locality_exhaustion(self):
        # Test that we use the same provider for multiple nodes within
        # a request if possible.  This exhausts the launch attempts on
        # one provider and ensures that we shift both nodes to the
        # second provider.

        # This test requests a pair of nodes, and causes the first
        # attempt of both nodes to fail; they will both be retried on
        # the same provider.  The second attempt of the first node
        # will also fail, causing it to be retried on the other
        # provider.  The second attempt of the second node succeeds,
        # but is nonetheless retried on the second provider in order
        # to preserve locality.
        self.waitUntilSettled()

        orig_advance = zuul.launcher.server.NodescanRequest.advance
        failed_count_by_node = {}

        def my_advance(*args, **kw):
            ns_request = args[0]
            failed_nodes = len(failed_count_by_node.keys())
            if failed_nodes > 2:
                return orig_advance(*args, **kw)
            failed_count = failed_count_by_node.get(
                ns_request.node.uuid, 0)
            failed_count_by_node[ns_request.node.uuid] = failed_count + 1
            raise Exception("Test exception")

        with mock.patch.object(
            zuul.launcher.server.NodescanRequest, 'advance', my_advance
        ):
            request1 = self.requestNodes(["debian-normal", "debian-normal"],
                                         tenant="tenant-two",
                                         timeout=30)
        nodes1 = self.getNodes(request1)
        nodes1 = [n for n in nodes1 if n.state == n.State.READY]
        nodes1 = [n for n in nodes1 if n.uuid in request1.nodes]
        self.assertEqual(2, len(nodes1))

        # These can be served from either provider; both should be
        # assigned to the same one.
        self.assertEqual(nodes1[0].provider, nodes1[1].provider)

        # There should be 3 total ready nodes, one unattached, so wait
        # for the failed nodes to be deleted to avoid test cleanup
        # races.
        for _ in iterate_timeout(60, "extra nodes to be deleted"):
            if len(self.launcher.api.nodes_cache.getItems()) == 3:
                break

    @okay_tracebacks('_checkNodescanRequest')
    def test_provider_selection_locality_exhaustion_failure(self):
        # Test that we use the same provider for multiple nodes within
        # a request if possible.  This exhausts the launch attempts on
        # both providers and ensures that we fail the request.
        self.waitUntilSettled()

        def my_advance(*args, **kw):
            raise Exception("Test exception")

        with mock.patch.object(
            zuul.launcher.server.NodescanRequest, 'advance', my_advance
        ):
            request1 = self.requestNodes(["debian-normal", "debian-normal"],
                                         tenant="tenant-two",
                                         timeout=30)
        self.assertEqual(request1.state, model.NodesetRequest.State.FAILED)

        # The last two nodes will still be referenced by the request,
        # so delete the request to release them.
        ctx = self.createZKContext(None)
        request1.delete(ctx)
        self.waitUntilSettled()

        # All nodes failed, so all should be deleted; wait for that to
        # happen to avoid test cleanup races.
        for _ in iterate_timeout(60, "extra nodes to be deleted"):
            if len(self.launcher.api.nodes_cache.getItems()) == 0:
                break


class TestLauncherUpload(LauncherBaseTestCase):

    def setUp(self):
        self._ubuntu_images = []
        self.useFixture(fixtures.MonkeyPatch(
            'zuul.driver.aws.awsendpoint.AwsImageUploadJob.run',
            self._upload_run))
        super().setUp()

    def _waitForArtifacts(self, image_name, count, format=None):
        for _ in iterate_timeout(30, "artifacts to settle"):
            artifacts = self.launcher.image_build_registry.\
                getArtifactsForImage(image_name)
            if format:
                artifacts = [a for a in artifacts if a.format == format]
            if len(artifacts) == count:
                return artifacts

    def _waitForUploads(self, image_name, count):
        for _ in iterate_timeout(30, "uploads to settle"):
            uploads = self.launcher.image_upload_registry.\
                getUploadsForImage(image_name)
            if len(uploads) == count:
                return uploads

    def _upload_run(test, self, *args, **kw):
        # Fail on first upload of this image
        if 'ubuntu-local' in self.image_name:
            upload_id = self.metadata['zuul_upload_uuid']
            upload = test.launcher.image_upload_registry.getItem(upload_id)
            artifact_id = upload.artifact_uuid
            if artifact_id not in test._ubuntu_images:
                test._ubuntu_images.append(artifact_id)
            if test._ubuntu_images[0] == artifact_id:
                test._addFinishedUpload(upload_id)
                raise Exception("Upload test failure")
        return "test_external_id"

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
    @okay_tracebacks('Upload test failure')
    def test_launcher_image_expire_failed_upload(self):
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
            artifacts = self._waitForArtifacts(name, 1, format='raw')
            self._waitForArtifacts(name, 0, format='qcow2')
            self.assertEqual('raw', artifacts[0].format)
            self.assertTrue(artifacts[0].validated)
            uploads = self._waitForUploads(name, 1)
            self.assertEqual(artifacts[0].uuid, uploads[0].artifact_uuid)
            if 'ubuntu' in name:
                self.assertIsNone(uploads[0].external_id)
            else:
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
        artifacts = self._waitForArtifacts(image_cname, 2, format='raw')
        oldest_artifact_uuid = artifacts[0].uuid

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
        # Trigger a run of the deletion check.
        self.launcher.upload_deleted_event.set()
        self.launcher.wake_event.set()
        self.waitUntilSettled()
        artifacts = self._waitForArtifacts(image_cname, 2, format='raw')
        artifact_uuids = [x.uuid for x in artifacts]
        self.assertNotIn(oldest_artifact_uuid, artifact_uuids)


class TestMinReadyLauncher(LauncherBaseTestCase):
    tenant_config_file = "config/launcher-min-ready/main.yaml"

    def test_min_ready(self):
        # tenant-one:
        #   common-config:
        #     Provider aws-us-east-1-main
        #       debian-normal (t3.medium)  (hash A)
        #   project1:
        #     Provider aws-ca-central-1-main
        #       debian-normal (t3.small)   (hash B)
        # tenant-two:
        #   common-config:
        #     Provider aws-us-east-1-main
        #       debian-normal (t3.medium)  (hash A)

        # min-ready=2 for debian-normal
        #   2 from aws-us-east-1-main
        #   0-2 from aws-ca-central-1-main
        # min-ready=1 for debian-emea
        #   1 from aws-eu-central-1-main
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

        # Make sure the ready nodes show up in stats, even though they
        # are not on a provider.
        self.launcher._runStats()
        pname = 'review_example_com%2Fcommon-config/aws-us-east-1-main'
        self.assertReportedStat(
            f'zuul.provider.{pname}.label.debian-normal.nodes.state.ready',
            value='2',
            kind='g')
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
            # project2 will definitely use a ready node; project1 may
            # or may not depending on which providers were selected
            # for ready nodes and nodeset requests.
            in_use_nodes = [n for n in nodes if n.state == n.State.IN_USE]
            if len(in_use_nodes) >= 1:
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

        self.waitUntilSettled('start')
        nodes = self.launcher.api.nodes_cache.getItems()
        self.assertGreaterEqual(len(nodes), 3)
        self.assertLessEqual(len(nodes), 5)

        nodes_by_label = self._nodes_by_label()
        self.assertEqual(1, len(nodes_by_label['debian-emea']))
        node = nodes_by_label['debian-emea'][0]
        ctx = self.createZKContext(None)
        # Make a new copy so we can obtain our own lock
        node = model.ProviderNode.fromZK(ctx, path=node.getPath())
        try:
            node.acquireLock(ctx)
            node.updateAttributes(ctx, state_time=0)
        finally:
            node.releaseLock(ctx)

        for _ in iterate_timeout(60, "node to be deleted"):
            try:
                node.refresh(ctx)
            except NoNodeError:
                break

        self.waitUntilSettled('deleted')
        for _ in iterate_timeout(60, "node to be replaced"):
            nodes = self.launcher.api.nodes_cache.getItems()
            if node in nodes:
                continue
            if not 3 <= len(nodes) <= 5:
                continue
            if all(n.state == n.State.READY for n in nodes):
                break

        self.waitUntilSettled('replaced')
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


class TestNodepoolAbsent(LauncherBaseTestCase):
    tenant_config_file = 'config/nodepool-absent/main.yaml'

    def test_normal_label(self):
        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A')
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='debian-normal-job', result='SUCCESS', changes='1,1'),
        ], ordered=False)

    def test_unattached_label(self):
        in_repo_conf = textwrap.dedent(
            """
            - project:
                check:
                  jobs:
                    - debian-unattached-job
            """)
        file_dict = {'zuul.yaml': in_repo_conf}
        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A',
                                           files=file_dict)
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()
        self.assertEqual(A.data['status'], 'NEW')
        self.assertEqual(A.reported, 1)
        self.assertTrue(re.search('debian-unattached-job .* NODE_FAILURE',
                                  A.messages[0]))

    def test_missing_label(self):
        in_repo_conf = textwrap.dedent(
            """
            - job:
                name: debian-missing-job
                nodeset:
                  nodes:
                    - label: debian-missing
                      name: controller
            - project:
                check:
                  jobs:
                    - debian-missing-job
            """)
        file_dict = {'zuul.yaml': in_repo_conf}
        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A',
                                           files=file_dict)
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()
        self.assertEqual(A.patchsets[0]['approvals'][0]['value'], "-1")
        self.assertIn('The label "debian-missing" was not found',
                      A.messages[0],
                      "A should have failed the check pipeline")
