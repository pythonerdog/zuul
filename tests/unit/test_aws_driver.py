# Copyright 2024-2025 Acme Gating, LLC
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

import base64
import concurrent.futures
import contextlib
import ipaddress
import time
from unittest import mock
import urllib.parse

import fixtures
from moto import mock_aws
import boto3
import botocore.exceptions

from zuul.driver.aws import AwsDriver
from zuul.driver.aws.awsmodel import AwsProviderNode
import zuul.driver.aws.awsendpoint

from tests.fake_aws import FakeAws, FakeAwsProviderEndpoint
from tests.base import (
    iterate_timeout,
    simple_layout,
    return_data,
    driver_config,
)
from tests.unit.test_launcher import ImageMocksFixture
from tests.unit.test_cloud_driver import BaseCloudDriverTest


def _make_ipv6_subnets(cidr_block):
    network = ipaddress.IPv6Network(cidr_block)
    # AWS only supports /64 prefix length
    return [str(sn) for sn in network.subnets(new_prefix=64)]


class TestAwsDriver(BaseCloudDriverTest):
    config_file = 'zuul-connections-nodepool.conf'
    cloud_test_image_format = 'raw'
    cloud_test_provider_name = 'aws-us-east-1-main'
    mock_aws = mock_aws()
    debian_return_data = {
        'zuul': {
            'artifacts': [
                {
                    'name': 'raw image',
                    'url': 'http://example.com/image.raw',
                    'metadata': {
                        'type': 'zuul_image',
                        'image_name': 'debian-local',
                        'format': 'raw',
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
        aws_id = 'AK000000000000000000'
        aws_key = '0123456789abcdef0123456789abcdef0123456789abcdef'
        self.useFixture(
            fixtures.EnvironmentVariable('AWS_ACCESS_KEY_ID', aws_id))
        self.useFixture(
            fixtures.EnvironmentVariable('AWS_SECRET_ACCESS_KEY', aws_key))
        self.patch(zuul.driver.aws.awsendpoint, 'CACHE_TTL', 1)

        self.fake_aws = FakeAws()
        self.mock_aws.start()
        # Must start responses after mock_aws
        self.useFixture(ImageMocksFixture())

        self.ec2 = boto3.resource('ec2', region_name='us-east-1')
        self.ec2_client = boto3.client('ec2', region_name='us-east-1')
        self.s3 = boto3.resource('s3', region_name='us-east-1')
        self.s3_client = boto3.client('s3', region_name='us-east-1')
        self.iam = boto3.resource('iam', region_name='us-east-1')
        self.s3.create_bucket(Bucket='zuul')

        # A list of args to method calls for validation
        self.run_instances_calls = []
        self.run_instances_exception = None
        self.create_fleet_calls = []
        self.create_fleet_results = []
        self.create_fleet_exception = None
        self.allocate_hosts_exception = None
        self.register_image_calls = []

        # TEST-NET-3
        self.subnet_ids = []
        ipv6 = False
        if ipv6:
            # This is currently unused, but if moto gains IPv6 support
            # on instance creation, this may be useful.
            self.vpc = self.ec2_client.create_vpc(
                CidrBlock='203.0.113.0/24',
                AmazonProvidedIpv6CidrBlock=True)
            ipv6_cidr = self.vpc['Vpc'][
                'Ipv6CidrBlockAssociationSet'][0]['Ipv6CidrBlock']
            ipv6_subnets = _make_ipv6_subnets(ipv6_cidr)

            subnet1 = self.ec2_client.create_subnet(
                AvailabilityZone='us-east-1a',
                CidrBlock='203.0.113.64/26',
                Ipv6CidrBlock=ipv6_subnets[0],
                VpcId=self.vpc['Vpc']['VpcId'])
            self.subnet_ids.append(subnet1['Subnet']['SubnetId'])
            subnet2 = self.ec2_client.create_subnet(
                AvailabilityZone='us-east-1b',
                CidrBlock='203.0.113.128/26',
                Ipv6CidrBlock=ipv6_subnets[1],
                VpcId=self.vpc['Vpc']['VpcId'])
            self.subnet_ids.append(subnet2['Subnet']['SubnetId'])
        else:
            self.vpc = self.ec2_client.create_vpc(CidrBlock='203.0.113.0/24')
            subnet1 = self.ec2_client.create_subnet(
                AvailabilityZone='us-east-1a',
                CidrBlock='203.0.113.64/26',
                VpcId=self.vpc['Vpc']['VpcId'])
            self.subnet_ids.append(subnet1['Subnet']['SubnetId'])
            subnet2 = self.ec2_client.create_subnet(
                AvailabilityZone='us-east-1b',
                CidrBlock='203.0.113.128/26',
                VpcId=self.vpc['Vpc']['VpcId'])
            self.subnet_ids.append(subnet2['Subnet']['SubnetId'])

        self.security_group = self.ec2_client.create_security_group(
            GroupName='zuul-nodes', VpcId=self.vpc['Vpc']['VpcId'],
            Description='Zuul Nodes')
        self.security_group_id = self.security_group['GroupId']
        self.profile = self.iam.create_instance_profile(
            InstanceProfileName='not-a-real-profile')

        self.patch(AwsDriver, '_endpoint_class', FakeAwsProviderEndpoint)
        self.patch(FakeAwsProviderEndpoint,
                   '_FakeAwsProviderEndpoint__testcase', self)

        default_ec2_quotas = {
            'L-1216C47A': 100,
            'L-43DA4232': 100,
            'L-34B43A08': 100,
        }
        default_ebs_quotas = {
            'L-D18FCD1D': 100.0,
            'L-7A658B76': 100.0,
        }
        ec2_quotas = self.test_config.driver.aws.get(
            'ec2_quotas', default_ec2_quotas)
        ebs_quotas = self.test_config.driver.aws.get(
            'ebs_quotas', default_ebs_quotas)
        self.patch(FakeAwsProviderEndpoint,
                   '_FakeAwsProviderEndpoint__ec2_quotas', ec2_quotas)
        self.patch(FakeAwsProviderEndpoint,
                   '_FakeAwsProviderEndpoint__ebs_quotas', ebs_quotas)

        super().setUp()

    def shutdown(self):
        super().shutdown()
        self.mock_aws.stop()

    def _assertProviderNodeAttributes(self, pnode):
        super()._assertProviderNodeAttributes(pnode)
        if checks := self.test_config.driver.aws.get('node_checks'):
            checks(self, pnode)

    def check_node_attrs(self, pnode):
        self.assertEqual(
            1000,
            self.run_instances_calls[0]['BlockDeviceMappings'][0]['Ebs']
            ['Iops'])
        self.assertEqual(
            200,
            self.run_instances_calls[0]['BlockDeviceMappings'][0]['Ebs']
            ['Throughput'])

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    @driver_config('aws', node_checks=check_node_attrs)
    def test_aws_node_lifecycle(self):
        self._test_node_lifecycle('debian-normal')

    def check_spot_node_attrs(self, pnode):
        # The basic test above sets few options; we set many more
        # options in the spot check (so that we don't have run a test
        # for every option).
        self.assertEqual(
            'spot',
            self.run_instances_calls[0]['InstanceMarketOptions']['MarketType'])
        self.assertEqual(
            'us-east-1b',
            self.run_instances_calls[0]['Placement']['AvailabilityZone'])
        self.assertEqual(
            ['testgroup'],
            self.run_instances_calls[0]['NetworkInterfaces'][0]['Groups'])
        self.assertEqual(
            1,
            self.run_instances_calls[0]['NetworkInterfaces'][0][
                'Ipv6AddressCount'])
        self.assertEqual(
            'required',
            self.run_instances_calls[0]['MetadataOptions']['HttpTokens'])
        self.assertTrue(pnode.node_properties['spot'])
        instance = self.ec2_client.describe_instance_attribute(
            InstanceId=pnode.aws_instance_id,
            Attribute='userData',
        )
        expected = base64.b64encode(b'testuserdata').decode('utf8')
        self.assertEqual(expected, instance['UserData']['Value'])

    @simple_layout('layouts/aws/spot.yaml', enable_nodepool=True,
                   replace=lambda test: {
                       'subnet_ids': test.subnet_ids,
                       'iam_profile_name': test.profile.name,
                   })
    @driver_config('aws', node_checks=check_spot_node_attrs)
    def test_aws_node_lifecycle_spot(self):
        self._test_node_lifecycle('debian-normal')

    def check_fleet_node_attrs(self, pnode):
        self.assertEqual(
            'price-capacity-optimized',
            self.create_fleet_calls[0]['OnDemandOptions'][
                'AllocationStrategy'])
        self.assertTrue(pnode.node_properties['fleet'])
        instance = self.ec2_client.describe_instance_attribute(
            InstanceId=pnode.aws_instance_id,
            Attribute='userData',
        )
        expected = base64.b64encode(b'testuserdata').decode('utf8')
        self.assertEqual(expected, instance['UserData']['Value'])

    @simple_layout('layouts/aws/fleet.yaml', enable_nodepool=True)
    @driver_config('aws', node_checks=check_fleet_node_attrs)
    def test_aws_node_lifecycle_fleet(self):
        self._test_node_lifecycle('debian-normal')
        self.waitUntilSettled()

        # Verify that we clean up unused launch templates.  Start by
        # checking that we have one from the current config.
        launch_tempaltes = self.ec2_client.\
            describe_launch_templates()['LaunchTemplates']
        self.assertEqual(len(launch_tempaltes), 1)

        # Switch to a config that has no fleet usage (spot is
        # arbitrary).
        self.commitConfigUpdate(
            'org/common-config', 'layouts/aws/spot.yaml',
            replace=lambda test: {
                'subnet_ids': test.subnet_ids,
                'iam_profile_name': test.profile.name,
            })

        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()

        # Verify that there are no launch templates.
        launch_tempaltes = self.ec2_client.\
            describe_launch_templates()['LaunchTemplates']
        self.assertEqual(len(launch_tempaltes), 0)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    @driver_config('aws', ec2_quotas={
        'L-1216C47A': 2,
    })
    def test_aws_quota(self):
        self._test_quota('debian-normal')

    @simple_layout('layouts/aws/resource-limits.yaml', enable_nodepool=True)
    def test_aws_resource_limits(self):
        self._test_quota('debian-normal')

    @simple_layout('layouts/aws/nodepool-image-snapshot.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        debian_return_data,
    )
    def test_aws_diskimage_snapshot(self):
        self._test_diskimage()

    @simple_layout('layouts/aws/nodepool-image-image.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        debian_return_data,
    )
    def test_aws_diskimage_image(self):
        self._test_diskimage()

    @simple_layout('layouts/aws/nodepool-image-ebs-direct.yaml',
                   enable_nodepool=True)
    @return_data(
        'build-debian-local-image',
        'refs/heads/master',
        debian_return_data,
    )
    def test_aws_diskimage_ebs_direct(self):
        self._test_diskimage()

    @simple_layout('layouts/nodepool-multi-provider.yaml',
                   enable_nodepool=True)
    def test_aws_resource_cleanup(self):
        self.waitUntilSettled()
        self.launcher.cleanup_worker.INTERVAL = 1
        # This tests everything except the image imports
        # Start by setting up leaked resources
        system_id = self.launcher.system.system_id
        instance_tags = [
            {'Key': 'zuul_system_id', 'Value': system_id},
            {'Key': 'zuul_node_uuid', 'Value': '0000000042'},
        ]

        s3_tags = {
            'zuul_system_id': system_id,
            'zuul_upload_uuid': '0000000042',
        }

        reservation = self.ec2_client.run_instances(
            ImageId="ami-12c6146b", MinCount=1, MaxCount=1,
            BlockDeviceMappings=[{
                'DeviceName': '/dev/sda1',
                'Ebs': {
                    'VolumeSize': 80,
                    'DeleteOnTermination': False
                }
            }],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': instance_tags
            }, {
                'ResourceType': 'volume',
                'Tags': instance_tags
            }]
        )
        instance_id = reservation['Instances'][0]['InstanceId']

        bucket = self.s3.Bucket('zuul')
        bucket.put_object(Body=b'hi',
                          Key='testimage',
                          Tagging=urllib.parse.urlencode(s3_tags))
        obj = self.s3.Object('zuul', 'testimage')
        # This effectively asserts the object exists
        self.s3_client.get_object_tagging(
            Bucket=obj.bucket_name, Key=obj.key)

        instance = self.ec2.Instance(instance_id)
        self.assertEqual(instance.state['Name'], 'running')

        volume_id = list(instance.volumes.all())[0].id
        volume = self.ec2.Volume(volume_id)
        self.assertEqual(volume.state, 'in-use')

        self.log.debug("Start cleanup worker")
        self.launcher.cleanup_worker.start()

        for _ in iterate_timeout(30, 'instance deletion'):
            instance = self.ec2.Instance(instance_id)
            if instance.state['Name'] == 'terminated':
                break
            time.sleep(1)

        for _ in iterate_timeout(30, 'volume deletion'):
            volume = self.ec2.Volume(volume_id)
            try:
                if volume.state == 'deleted':
                    break
            except botocore.exceptions.ClientError:
                # Probably not found
                break
            time.sleep(1)

        for _ in iterate_timeout(30, 'object deletion'):
            obj = self.s3.Object('zuul', 'testimage')
            try:
                self.s3_client.get_object_tagging(
                    Bucket=obj.bucket_name, Key=obj.key)
            except self.s3_client.exceptions.NoSuchKey:
                break
            time.sleep(1)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_aws_resource_cleanup_import_snapshot(self):
        # This tests the import_snapshot path
        self.waitUntilSettled()
        self.launcher.cleanup_worker.INTERVAL = 1
        system_id = self.launcher.system.system_id

        # Start by setting up leaked resources
        image_tags = [
            {'Key': 'zuul_system_id', 'Value': system_id},
            {'Key': 'zuul_upload_uuid', 'Value': '0000000042'},
        ]

        task = self.fake_aws.import_snapshot(
            DiskContainer={
                'Format': 'ova',
                'UserBucket': {
                    'S3Bucket': 'zuul',
                    'S3Key': 'testfile',
                }
            },
            TagSpecifications=[{
                'ResourceType': 'import-snapshot-task',
                'Tags': image_tags,
            }])
        snapshot_id = self.fake_aws.finish_import_snapshot(task)

        register_response = self.ec2_client.register_image(
            Architecture='amd64',
            BlockDeviceMappings=[
                {
                    'DeviceName': '/dev/sda1',
                    'Ebs': {
                        'DeleteOnTermination': True,
                        'SnapshotId': snapshot_id,
                        'VolumeSize': 20,
                        'VolumeType': 'gp2',
                    },
                },
            ],
            RootDeviceName='/dev/sda1',
            VirtualizationType='hvm',
            Name='testimage',
        )
        image_id = register_response['ImageId']

        ami = self.ec2.Image(image_id)
        new_snapshot_id = ami.block_device_mappings[0]['Ebs']['SnapshotId']
        self.fake_aws.change_snapshot_id(task, new_snapshot_id)

        # Note that the resulting image and snapshot do not have tags
        # applied, so we test the automatic retagging methods in the
        # adapter.

        image = self.ec2.Image(image_id)
        self.assertEqual(image.state, 'available')

        snap = self.ec2.Snapshot(snapshot_id)
        self.assertEqual(snap.state, 'completed')

        # Now that the leaked resources exist, start the worker and
        # wait for it to clean them.
        self.log.debug("Start cleanup worker")
        self.launcher.cleanup_worker.start()

        for _ in iterate_timeout(30, 'ami deletion'):
            image = self.ec2.Image(image_id)
            try:
                # If this has a value the image was not deleted
                if image.state == 'available':
                    # Definitely not deleted yet
                    pass
            except AttributeError:
                # Per AWS API, a recently deleted image is empty and
                # looking at the state raises an AttributeFailure; see
                # https://github.com/boto/boto3/issues/2531.  The image
                # was deleted, so we continue on here
                break
            time.sleep(1)

        for _ in iterate_timeout(30, 'snapshot deletion'):
            snap = self.ec2.Snapshot(new_snapshot_id)
            try:
                if snap.state == 'deleted':
                    break
            except botocore.exceptions.ClientError:
                # Probably not found
                break
            time.sleep(1)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_aws_resource_cleanup_import_image(self):
        # This tests the import_image path
        self.waitUntilSettled()
        self.launcher.cleanup_worker.INTERVAL = 1
        system_id = self.launcher.system.system_id

        # Start by setting up leaked resources
        image_tags = [
            {'Key': 'zuul_system_id', 'Value': system_id},
            {'Key': 'zuul_upload_uuid', 'Value': '0000000042'},
        ]

        # The image import path:
        task = self.fake_aws.import_image(
            DiskContainers=[{
                'Format': 'ova',
                'UserBucket': {
                    'S3Bucket': 'zuul',
                    'S3Key': 'testfile',
                }
            }],
            TagSpecifications=[{
                'ResourceType': 'import-image-task',
                'Tags': image_tags,
            }])
        image_id, snapshot_id = self.fake_aws.finish_import_image(task)

        # Note that the resulting image and snapshot do not have tags
        # applied, so we test the automatic retagging methods in the
        # adapter.

        image = self.ec2.Image(image_id)
        self.assertEqual(image.state, 'available')

        snap = self.ec2.Snapshot(snapshot_id)
        self.assertEqual(snap.state, 'completed')

        # Now that the leaked resources exist, start the provider and
        # wait for it to clean them.
        # Now that the leaked resources exist, start the worker and
        # wait for it to clean them.
        self.log.debug("Start cleanup worker")
        self.launcher.cleanup_worker.start()

        for _ in iterate_timeout(30, 'ami deletion'):
            image = self.ec2.Image(image_id)
            try:
                # If this has a value the image was not deleted
                if image.state == 'available':
                    # Definitely not deleted yet
                    pass
            except AttributeError:
                # Per AWS API, a recently deleted image is empty and
                # looking at the state raises an AttributeFailure; see
                # https://github.com/boto/boto3/issues/2531.  The image
                # was deleted, so we continue on here
                break
            time.sleep(1)

        for _ in iterate_timeout(30, 'snapshot deletion'):
            snap = self.ec2.Snapshot(snapshot_id)
            try:
                if snap.state == 'deleted':
                    break
            except botocore.exceptions.ClientError:
                # Probably not found
                break
            time.sleep(1)

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_state_machines_instance(self):
        self._test_state_machines("debian-normal")

    @simple_layout('layouts/nodepool.yaml', enable_nodepool=True)
    def test_state_machines_dedicated_host(self):
        self._test_state_machines("debian-dedicated")

    def _test_state_machines(self, label):
        # Stop the launcher main loop, so we can drive the state machine
        # on our own.
        self.waitUntilSettled()
        self.launcher._running = False
        self.launcher.wake_event.set()
        self.launcher.launcher_thread.join()

        layout = self.scheds.first.sched.abide.tenants.get('tenant-one').layout
        provider = layout.providers['aws-us-east-1-main']
        # Start the endpoint since we're going to use the scheduler's endpoint.
        provider.getEndpoint().start()

        with self.createZKContext(None) as ctx:
            node = AwsProviderNode.new(ctx, label=label)
            execute_future = False
            for _ in iterate_timeout(60, "create state machine to complete"):
                with node.activeContext(ctx):
                    # Re-create the SM from the state in ZK
                    sm = provider.getCreateStateMachine(node, None, self.log)
                    node.create_state_machine = sm
                    with self._block_futures():
                        sm.advance()
                    # If there are pending futures we will try to re-create
                    # the SM once from the state and then advance it once
                    # more so the futures can complete.
                    pending_futures = [
                        f for f in (sm.host_create_future, sm.create_future)
                        if f]
                    if pending_futures:
                        if execute_future:
                            concurrent.futures.wait(pending_futures)
                            sm.advance()
                        # Toggle future execution flag
                        execute_future = not execute_future
                if sm.complete:
                    break

            for _ in iterate_timeout(60, "delete state machine to complete"):
                with node.activeContext(ctx):
                    # Re-create the SM from the state in ZK
                    sm = provider.getDeleteStateMachine(node, self.log)
                    node.delete_state_machine = sm
                    sm.advance()
                if sm.complete:
                    break
                # Avoid busy-looping as we have to wait for the TTL
                # cache to expire.
                time.sleep(0.5)

    @contextlib.contextmanager
    def _block_futures(self):
        with (mock.patch(
                'zuul.driver.aws.awsendpoint.AwsProviderEndpoint.'
                '_completeAllocateHost', return_value=None),
              mock.patch(
                'zuul.driver.aws.awsendpoint.AwsProviderEndpoint.'
                '_completeCreateInstance', return_value=None)):
            yield
