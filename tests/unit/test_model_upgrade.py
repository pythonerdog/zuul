# Copyright 2022, 2024 Acme Gating, LLC
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

from zuul.zk.components import (
    COMPONENT_REGISTRY,
    ComponentRegistry,
    SchedulerComponent,
)
from tests.base import (
    BaseTestCase,
    ZuulTestCase,
    gerrit_config,
    simple_layout,
    iterate_timeout,
    model_version,
    ZOOKEEPER_SESSION_TIMEOUT,
)
from zuul import model
from zuul.zk import ZooKeeperClient
from zuul.zk.branch_cache import BranchCache, BranchFlag
from zuul.zk.locks import management_queue_lock
from zuul.zk.zkobject import ZKContext
from tests.unit.test_zk import DummyConnection


class TestModelUpgrade(ZuulTestCase):
    tenant_config_file = "config/single-tenant/main-model-upgrade.yaml"
    scheduler_count = 1

    def getJobData(self, tenant, pipeline):
        item_path = f'/zuul/tenant/{tenant}/pipeline/{pipeline}/item'
        count = 0
        for item in self.zk_client.client.get_children(item_path):
            bs_path = f'{item_path}/{item}/buildset'
            for buildset in self.zk_client.client.get_children(bs_path):
                data = json.loads(self.getZKObject(
                    f'{bs_path}/{buildset}/job/check-job'))
                count += 1
                yield data
        if not count:
            raise Exception("No job data found")

    @model_version(0)
    @simple_layout('layouts/simple.yaml')
    def test_model_upgrade_0_1(self):
        component_registry = ComponentRegistry(self.zk_client)
        self.assertEqual(component_registry.model_api, 0)

        # Upgrade our component
        self.model_test_component_info.model_api = 1

        for _ in iterate_timeout(30, "model api to update"):
            if component_registry.model_api == 1:
                break

    @model_version(33)
    def test_model_upgrade_33_34(self):

        attrs = model.SystemAttributes.fromDict({
            "use_relative_priority": True,
            "max_hold_expiration": 7200,
            "default_hold_expiration": 3600,
            "default_ansible_version": "X",
            "web_root": "/web/root",
            "websocket_url": "/web/socket",
            "web_status_url": "ignored",
        })

        attr_dict = attrs.toDict()
        self.assertIn("web_status_url", attr_dict)
        self.assertEqual(attr_dict["web_status_url"], "")

        # Upgrade our component
        self.model_test_component_info.model_api = 34

        component_registry = ComponentRegistry(self.zk_client)
        for _ in iterate_timeout(30, "model api to update"):
            if component_registry.model_api == 34:
                break

        attr_dict = attrs.toDict()
        self.assertNotIn("web_status_url", attr_dict)


class TestModelUpgradeGerritCircularDependencies(ZuulTestCase):
    config_file = "zuul-gerrit-github.conf"
    tenant_config_file = "config/circular-dependencies/main.yaml"

    @model_version(31)
    @gerrit_config(submit_whole_topic=True)
    def test_model_31_32(self):
        self.executor_server.hold_jobs_in_build = True

        A = self.fake_gerrit.addFakeChange('org/project1', "master", "A",
                                           topic='test-topic')
        B = self.fake_gerrit.addFakeChange('org/project2', "master", "B",
                                           topic='test-topic')

        A.addApproval("Code-Review", 2)
        B.addApproval("Code-Review", 2)
        B.addApproval("Approved", 1)

        self.fake_gerrit.addEvent(A.addApproval("Approved", 1))
        self.waitUntilSettled()

        first = self.scheds.first
        second = self.createScheduler()
        second.start()
        self.assertEqual(len(self.scheds), 2)
        for _ in iterate_timeout(10, "until priming is complete"):
            state_one = first.sched.local_layout_state.get("tenant-one")
            if state_one:
                break

        for _ in iterate_timeout(
                10, "all schedulers to have the same layout state"):
            if (second.sched.local_layout_state.get(
                    "tenant-one") == state_one):
                break

        self.model_test_component_info.model_api = 32
        with first.sched.layout_update_lock, first.sched.run_handler_lock:
            self.fake_gerrit.addEvent(A.addApproval("Approved", 1))
            self.waitUntilSettled(matcher=[second])

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()
        self.assertEqual(A.data["status"], "MERGED")
        self.assertEqual(B.data["status"], "MERGED")


class TestGithubModelUpgrade(ZuulTestCase):
    config_file = "zuul-gerrit-github.conf"
    scheduler_count = 1

    @model_version(26)
    @simple_layout('layouts/gate-github.yaml', driver='github')
    def test_model_26(self):
        # This excercises the backwards-compat branch cache
        # serialization code; no uprade happens in this test.
        first = self.scheds.first
        second = self.createScheduler()
        second.start()
        self.assertEqual(len(self.scheds), 2)
        for _ in iterate_timeout(10, "until priming is complete"):
            state_one = first.sched.local_layout_state.get("tenant-one")
            if state_one:
                break

        for _ in iterate_timeout(
                10, "all schedulers to have the same layout state"):
            if (second.sched.local_layout_state.get(
                    "tenant-one") == state_one):
                break

        conn = first.connections.connections['github']
        with self.createZKContext() as ctx:
            # There's a lot of exception catching in the branch cache,
            # so exercise a serialize/deserialize cycle.
            old = conn._branch_cache.cache.serialize(ctx)
            data = json.loads(old)
            self.assertEqual(['master'],
                             data['remainder']['org/common-config'])
            new = conn._branch_cache.cache.deserialize(old, ctx)
            self.assertTrue(new['projects'][
                'org/common-config'].branches['master'].present)

        with first.sched.layout_update_lock, first.sched.run_handler_lock:
            A = self.fake_github.openFakePullRequest(
                'org/project', 'master', 'A')
            self.fake_github.emitEvent(A.getPullRequestOpenedEvent())
            self.waitUntilSettled(matcher=[second])

        self.waitUntilSettled()
        self.assertHistory([
            dict(name='project-test1', result='SUCCESS'),
            dict(name='project-test2', result='SUCCESS'),
        ], ordered=False)

    @model_version(26)
    @simple_layout('layouts/gate-github.yaml', driver='github')
    def test_model_26_27(self):
        # This excercises the branch cache upgrade.
        first = self.scheds.first
        self.model_test_component_info.model_api = 27
        second = self.createScheduler()
        second.start()
        self.assertEqual(len(self.scheds), 2)
        for _ in iterate_timeout(10, "until priming is complete"):
            state_one = first.sched.local_layout_state.get("tenant-one")
            if state_one:
                break

        for _ in iterate_timeout(
                10, "all schedulers to have the same layout state"):
            if (second.sched.local_layout_state.get(
                    "tenant-one") == state_one):
                break

        with first.sched.layout_update_lock, first.sched.run_handler_lock:
            A = self.fake_github.openFakePullRequest(
                'org/project', 'master', 'A')
            self.fake_github.emitEvent(A.getPullRequestOpenedEvent())
            self.waitUntilSettled(matcher=[second])

        self.waitUntilSettled()
        self.assertHistory([
            dict(name='project-test1', result='SUCCESS'),
            dict(name='project-test2', result='SUCCESS'),
        ], ordered=False)

    @model_version(27)
    @simple_layout('layouts/two-projects-integrated.yaml')
    def test_model_27_28(self):
        # This excercises the repo state blobstore upgrade
        self.hold_merge_jobs_in_queue = True
        self.executor_server.hold_jobs_in_build = True

        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A')
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        jobs = list(self.merger_api.queued())
        self.merger_api.release(jobs[0])
        self.waitUntilSettled()

        # Perform the upgrade between the first and second merge jobs
        # to verify that we don't lose the data from the first merge
        # job.
        self.model_test_component_info.model_api = 28
        jobs = list(self.merger_api.queued())
        self.merger_api.release(jobs[0])
        self.waitUntilSettled()

        worker = list(self.executor_server.job_workers.values())[0]
        gerrit_repo_state = worker.repo_state['gerrit']
        self.assertTrue('org/common-config' in gerrit_repo_state)
        self.assertTrue('org/project1' in gerrit_repo_state)

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='integration', result='SUCCESS'),
        ], ordered=False)

    @model_version(28)
    @simple_layout('layouts/simple.yaml')
    def test_model_28(self):
        # This exercises the old side of the buildset
        # dependent_changes upgrade.  We don't need to perform an
        # upgrade in this test since the only behavior switch is on
        # the write side.  The read side will be tested in the new
        # case by the standard test suite, and in the old case by this
        # test.
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B')
        B.setDependsOn(A, 1)
        self.fake_gerrit.addEvent(B.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        A.setMerged()
        self.fake_gerrit.addEvent(A.getRefUpdatedEvent())
        self.waitUntilSettled()

        self.assertHistory([
            dict(name='check-job', result='SUCCESS'),
            dict(name='post-job', result='SUCCESS'),
        ], ordered=False)


class TestBranchCacheUpgrade(BaseTestCase):
    def setUp(self):
        super().setUp()

        self.setupZK()

        self.zk_client = ZooKeeperClient(
            self.zk_chroot_fixture.zk_hosts,
            tls_cert=self.zk_chroot_fixture.zookeeper_cert,
            tls_key=self.zk_chroot_fixture.zookeeper_key,
            tls_ca=self.zk_chroot_fixture.zookeeper_ca,
            timeout=ZOOKEEPER_SESSION_TIMEOUT,
        )
        self.addCleanup(self.zk_client.disconnect)
        self.zk_client.connect()
        self.model_test_component_info = SchedulerComponent(
            self.zk_client, 'test_component')
        self.model_test_component_info.register(26)
        self.component_registry = ComponentRegistry(self.zk_client)
        COMPONENT_REGISTRY.create(self.zk_client)

    def test_branch_cache_upgrade(self):
        conn = DummyConnection()
        cache = BranchCache(self.zk_client, conn, self.component_registry)

        # Test all of the different combinations of old branch cache data:

        # project0: failed both queries
        # project1: protected and queried both
        # project2: protected and only queried unprotected
        # project3: protected and only queried protected
        # project4: unprotected and queried both
        # project5: unprotected and only queried unprotected
        # project6: unprotected and only queried protected
        # project7: both and queried both
        # project8: both and only queried unprotected
        # project9: both and only queried protected

        data = {
            'default_branch': {},
            'merge_modes': {},
            'protected': {
                'project0': None,
                'project1': ['protected_branch'],
                # 'project2':
                'project3': ['protected_branch'],
                'project4': [],
                # 'project5':
                'project6': [],
                'project7': ['protected_branch'],
                # 'project8':
                'project9': ['protected_branch'],
            },
            'remainder': {
                'project0': None,
                'project1': [],
                'project2': ['protected_branch'],
                # 'project3':
                'project4': ['unprotected_branch'],
                'project5': ['unprotected_branch'],
                # 'project6':
                'project7': ['unprotected_branch'],
                'project8': ['protected_branch', 'unprotected_branch'],
                # 'project9':
            }
        }
        ctx = ZKContext(self.zk_client, None, None, self.log)
        data = json.dumps(data, sort_keys=True).encode("utf8")
        cache.cache._save(ctx, data)
        cache.cache.refresh(ctx)

        expected = {
            'project0': {
                'completed': BranchFlag.CLEAR,
                'failed': BranchFlag.PROTECTED | BranchFlag.PRESENT,
                'branches': {}
            },
            'project1': {
                'completed': BranchFlag.PROTECTED | BranchFlag.PRESENT,
                'failed': BranchFlag.CLEAR,
                'branches': {
                    'protected_branch': {'protected': True},
                }
            },
            'project2': {
                'completed': BranchFlag.PRESENT,
                'failed': BranchFlag.CLEAR,
                'branches': {
                    'protected_branch': {'present': True},
                }
            },
            'project3': {
                'completed': BranchFlag.PROTECTED,
                'failed': BranchFlag.CLEAR,
                'branches': {
                    'protected_branch': {'protected': True},
                }
            },
            'project4': {
                'completed': BranchFlag.PROTECTED | BranchFlag.PRESENT,
                'failed': BranchFlag.CLEAR,
                'branches': {
                    'unprotected_branch': {'present': True},
                }
            },
            'project5': {
                'completed': BranchFlag.PRESENT,
                'failed': BranchFlag.CLEAR,
                'branches': {
                    'unprotected_branch': {'present': True},
                }
            },
            'project6': {
                'completed': BranchFlag.PROTECTED,
                'failed': BranchFlag.CLEAR,
                'branches': {}
            },
            'project7': {
                'completed': BranchFlag.PROTECTED | BranchFlag.PRESENT,
                'failed': BranchFlag.CLEAR,
                'branches': {
                    'protected_branch': {'protected': True},
                    'unprotected_branch': {'present': True},
                }
            },
            'project8': {
                'completed': BranchFlag.PRESENT,
                'failed': BranchFlag.CLEAR,
                'branches': {
                    'protected_branch': {'present': True},
                    'unprotected_branch': {'present': True},
                }
            },
            'project9': {
                'completed': BranchFlag.PROTECTED,
                'failed': BranchFlag.CLEAR,
                'branches': {
                    'protected_branch': {'protected': True},
                }
            },
        }

        for project_name, project in expected.items():
            cache_project = cache.cache.projects[project_name]
            self.assertEqual(
                project['completed'],
                cache_project.completed_flags,
            )
            self.assertEqual(
                project['failed'],
                cache_project.failed_flags,
            )
            for branch_name, branch in project['branches'].items():
                cache_branch = cache_project.branches[branch_name]
                self.assertEqual(
                    branch.get('protected'),
                    cache_branch.protected,
                )
                self.assertEqual(
                    branch.get('present'),
                    cache_branch.present,
                )
            for branch_name in cache_project.branches.keys():
                if branch_name not in project['branches']:
                    raise Exception(f"Unexpected branch {branch_name}")


class TestSemaphoreReleaseUpgrade(ZuulTestCase):
    tenant_config_file = 'config/global-semaphores/main.yaml'

    @model_version(32)
    def test_model_32(self):
        # This tests that a job finishing in one tenant will correctly
        # start a job in another tenant waiting on the semaphore.
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A')
        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        B = self.fake_gerrit.addFakeChange('org/project2', 'master', 'B')
        self.fake_gerrit.addEvent(B.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        self.assertHistory([])
        self.assertBuilds([
            dict(name='test-global-semaphore', changes='1,1'),
        ])

        # Block tenant management event queues so we know that the
        # semaphore release events are dispatched via the pipeline
        # trigger event queue.
        with (management_queue_lock(self.zk_client, "tenant-one"),
              management_queue_lock(self.zk_client, "tenant-two")):

            self.executor_server.hold_jobs_in_build = False
            self.executor_server.release()
            self.waitUntilSettled()

            self.assertHistory([
                dict(name='test-global-semaphore',
                     result='SUCCESS', changes='1,1'),
                dict(name='test-global-semaphore',
                     result='SUCCESS', changes='2,1'),
            ], ordered=False)
