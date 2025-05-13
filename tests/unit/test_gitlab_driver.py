# Copyright 2019 Red Hat
# Copyright 2022 Acme Gating, LLC
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

import re
import os
import git
import yaml
import socket
import time

from zuul.lib import strings
from zuul.zk.layout import LayoutState
from zuul.zk.change_cache import ChangeKey

from tests.base import (
    ZuulTestCase,
    ZuulWebFixture,
    simple_layout,
    skipIfMultiScheduler,
)
from tests.util import random_sha1

from testtools.matchers import MatchesRegex

EMPTY_LAYOUT_STATE = LayoutState("", "", 0, None, {}, -1)


class TestGitlabWebhook(ZuulTestCase):
    config_file = 'zuul-gitlab-driver.conf'

    def setUp(self):
        super().setUp()

        # Start the web server
        self.web = self.useFixture(
            ZuulWebFixture(self.config, self.test_config,
                           self.additional_event_queues, self.upstream_root,
                           self.poller_events,
                           self.git_url_with_auth, self.addCleanup,
                           self.test_root))

        host = '127.0.0.1'
        # Wait until web server is started
        while True:
            port = self.web.port
            try:
                with socket.create_connection((host, port)):
                    break
            except ConnectionRefusedError:
                pass

        self.fake_gitlab.setZuulWebPort(port)

    def tearDown(self):
        super(TestGitlabWebhook, self).tearDown()

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_webhook(self):
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project', 'master', 'A')
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent(),
                                   use_zuulweb=False,
                                   project='org/project')
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_webhook_via_zuulweb(self):
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project', 'master', 'A')
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent(),
                                   use_zuulweb=True,
                                   project='org/project')
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)


class TestGitlabDriver(ZuulTestCase):
    config_file = 'zuul-gitlab-driver.conf'

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_opened(self):

        description = "This is the\nMR description."
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project', 'master', 'A', description=description)
        self.fake_gitlab.emitEvent(
            A.getMergeRequestOpenedEvent(), project='org/project')
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test2').result)

        job = self.getJobFromHistory('project-test2')
        zuulvars = job.parameters['zuul']
        self.assertEqual(str(A.number), zuulvars['change'])
        self.assertEqual(str(A.sha), zuulvars['patchset'])
        self.assertEqual(str(A.sha), zuulvars['commit_id'])
        self.assertEqual('master', zuulvars['branch'])
        self.assertEquals(f'{self.fake_gitlab._test_baseurl}/'
                          'org/project/merge_requests/1',
                          zuulvars['items'][0]['change_url'])
        self.assertEqual(zuulvars["message"], strings.b64encode(description))
        self.assertEqual(2, len(self.history))
        self.assertEqual(2, len(A.notes))
        self.assertEqual(
            A.notes[0]['body'], "Starting check jobs.")
        self.assertThat(
            A.notes[1]['body'],
            MatchesRegex(r'.*project-test1.*SUCCESS.*', re.DOTALL))
        self.assertThat(
            A.notes[1]['body'],
            MatchesRegex(r'.*project-test2.*SUCCESS.*', re.DOTALL))
        self.assertTrue(A.approved)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_opened_imcomplete(self):

        now = time.monotonic()
        complete_at = now + 3
        with self.fake_gitlab.enable_delayed_complete_mr(complete_at):
            description = "This is the\nMR description."
            A = self.fake_gitlab.openFakeMergeRequest(
                'org/project', 'master', 'A', description=description)
            self.fake_gitlab.emitEvent(
                A.getMergeRequestOpenedEvent(), project='org/project')
            self.waitUntilSettled()

            self.assertEqual('SUCCESS',
                             self.getJobFromHistory('project-test1').result)

            self.assertEqual('SUCCESS',
                             self.getJobFromHistory('project-test2').result)

        self.assertTrue(self.fake_gitlab._test_web_server.stats["get_mr"] > 2)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_updated(self):

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')
        mr_tip1_sha = A.sha
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))
        self.assertHistory(
            [
                {'name': 'project-test1', 'changes': '1,%s' % mr_tip1_sha},
                {'name': 'project-test2', 'changes': '1,%s' % mr_tip1_sha},
            ], ordered=False
        )

        self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
        mr_tip2_sha = A.sha
        self.waitUntilSettled()
        self.assertEqual(4, len(self.history))
        self.assertHistory(
            [
                {'name': 'project-test1', 'changes': '1,%s' % mr_tip1_sha},
                {'name': 'project-test2', 'changes': '1,%s' % mr_tip1_sha},
                {'name': 'project-test1', 'changes': '1,%s' % mr_tip2_sha},
                {'name': 'project-test2', 'changes': '1,%s' % mr_tip2_sha}
            ], ordered=False
        )

        # Adding or removing reviewer should not trigger a build
        self.fake_gitlab.emitEvent(A.getMergeRequestReviewersUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(4, len(self.history))

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_approved(self):

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')

        self.fake_gitlab.emitEvent(A.getMergeRequestApprovedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        self.fake_gitlab.emitEvent(A.getMergeRequestUnapprovedEvent())
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

        job = self.getJobFromHistory('project-test-approval')
        zuulvars = job.parameters['zuul']
        self.assertEqual('check-approval', zuulvars['pipeline'])

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_updated_during_build(self):

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        old = A.sha
        A.addCommit()
        new = A.sha
        self.assertNotEqual(old, new)
        self.waitUntilSettled()

        self.assertEqual(2, len(self.history))
        # MR must not be approved: tested commit isn't current commit
        self.assertFalse(A.approved)

        self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
        self.waitUntilSettled()

        self.assertEqual(4, len(self.history))
        self.assertTrue(A.approved)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_labeled(self):

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')

        self.fake_gitlab.emitEvent(A.getMergeRequestLabeledEvent(
            add_labels=('label1', 'label2')))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        self.fake_gitlab.emitEvent(A.getMergeRequestLabeledEvent(
            add_labels=('gateit', )))
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        A.labels = ['verified']
        self.fake_gitlab.emitEvent(A.getMergeRequestLabeledEvent(
            remove_labels=('verified', )))
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_merged(self):

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')

        self.fake_gitlab.emitEvent(A.getMergeRequestMergedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))
        self.assertHistory([{'name': 'project-promote'}])

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_push_does_not_reconfigure(self):
        # Test that the push event that follows a merge doesn't
        # needlessly trigger reconfiguration.

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')

        state1 = self.scheds.first.sched.local_layout_state.get("tenant-one")
        self.fake_gitlab.emitEvent(A.getMergeRequestMergedEvent())
        self.fake_gitlab.emitEvent(A.getMergeRequestMergedPushEvent(
            self.fake_gitlab))
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))
        self.assertHistory([{'name': 'project-post-job'},
                            {'name': 'project-promote'}
                            ], ordered=False)
        state2 = self.scheds.first.sched.local_layout_state.get("tenant-one")
        self.assertEqual(state1, state2)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_push_does_reconfigure(self):
        # Test that the push event that follows a merge does
        # trigger reconfiguration if .zuul.yaml is changed.

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')

        state1 = self.scheds.first.sched.local_layout_state.get("tenant-one")
        self.fake_gitlab.emitEvent(A.getMergeRequestMergedEvent())
        self.fake_gitlab.emitEvent(A.getMergeRequestMergedPushEvent(
            self.fake_gitlab,
            modified_files=['.zuul.yaml']))
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))
        self.assertHistory([{'name': 'project-post-job'},
                            {'name': 'project-promote'}
                            ], ordered=False)
        state2 = self.scheds.first.sched.local_layout_state.get("tenant-one")
        self.assertNotEqual(state1, state2)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_updated_builds_aborted(self):

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')
        mr_tip1_sha = A.sha

        self.executor_server.hold_jobs_in_build = True

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()

        self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
        mr_tip2_sha = A.sha
        self.waitUntilSettled()

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertHistory(
            [
                {'name': 'project-test1', 'result': 'ABORTED',
                 'changes': '1,%s' % mr_tip1_sha},
                {'name': 'project-test2', 'result': 'ABORTED',
                 'changes': '1,%s' % mr_tip1_sha},
                {'name': 'project-test1', 'changes': '1,%s' % mr_tip2_sha},
                {'name': 'project-test2', 'changes': '1,%s' % mr_tip2_sha}
            ], ordered=False
        )

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_dequeue_mr_abandoned(self):
        self.executor_server.hold_jobs_in_build = True

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        self.fake_gitlab.emitEvent(A.getMergeRequestClosedEvent())
        self.waitUntilSettled()

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual(2, len(self.history))
        self.assertEqual(2, self.countJobResults(self.history, 'ABORTED'))

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_commented(self):

        A = self.fake_gitlab.openFakeMergeRequest('org/project', 'master', 'A')
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

        self.fake_gitlab.emitEvent(
            A.getMergeRequestCommentedEvent('I like that change'))
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

        self.fake_gitlab.emitEvent(
            A.getMergeRequestCommentedEvent('recheck'))
        self.waitUntilSettled()
        self.assertEqual(4, len(self.history))

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    @skipIfMultiScheduler()
    # This test fails reproducibly with multiple schedulers because
    # the fake_gitlab._test_baseurl used in the assertion for the
    # change_url doesn't match.
    # An explanation for this would be that each scheduler (and the
    # test case itself) use different (fake) Gitlab connections.
    # However, the interesting part is that only this test fails
    # although there are other gitlab tests with a similar assertion.
    # Apart from that I'm wondering why this test first fails with
    # multiple schedulers as each scheduler should have a different
    # gitlab connection than the test case itself.
    def test_ref_updated(self):

        event = self.fake_gitlab.getPushEvent('org/project')
        expected_newrev = event[1]['after']
        expected_oldrev = event[1]['before']
        self.fake_gitlab.emitEvent(event)
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))
        self.assertEqual(
            'SUCCESS',
            self.getJobFromHistory('project-post-job').result)

        job = self.getJobFromHistory('project-post-job')
        zuulvars = job.parameters['zuul']
        self.assertEqual('refs/heads/master', zuulvars['ref'])
        self.assertEqual('post', zuulvars['pipeline'])
        self.assertEqual('project-post-job', zuulvars['job'])
        self.assertEqual('master', zuulvars['branch'])
        self.assertEqual(
            f'{self.fake_gitlab._test_baseurl}/org/project/tree/'
            f'{zuulvars["newrev"]}',
            zuulvars['change_url'])
        self.assertEqual(expected_newrev, zuulvars['newrev'])
        self.assertEqual(expected_oldrev, zuulvars['oldrev'])

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_ref_created(self):

        self.create_branch('org/project', 'stable-1.0')
        path = os.path.join(self.upstream_root, 'org/project')
        repo = git.Repo(path)
        newrev = repo.commit('refs/heads/stable-1.0').hexsha
        event = self.fake_gitlab.getPushEvent(
            'org/project', branch='refs/heads/stable-1.0',
            before='0' * 40, after=newrev)
        old = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)
        self.fake_gitlab.emitEvent(event)
        self.waitUntilSettled()
        new = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)
        # New timestamp should be greater than the old timestamp
        self.assertLess(old, new)
        self.assertEqual(1, len(self.history))
        self.assertEqual(
            'SUCCESS',
            self.getJobFromHistory('project-post-job').result)
        job = self.getJobFromHistory('project-post-job')
        zuulvars = job.parameters['zuul']
        self.assertEqual('refs/heads/stable-1.0', zuulvars['ref'])
        self.assertEqual('post', zuulvars['pipeline'])
        self.assertEqual('project-post-job', zuulvars['job'])
        self.assertEqual('stable-1.0', zuulvars['branch'])
        self.assertEqual(newrev, zuulvars['newrev'])

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_ref_deleted(self):

        event = self.fake_gitlab.getPushEvent(
            'org/project', 'stable-1.0', after='0' * 40)
        self.fake_gitlab.emitEvent(event)
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_tag_created(self):

        path = os.path.join(self.upstream_root, 'org/project')
        repo = git.Repo(path)
        repo.create_tag('1.0')
        tagsha = repo.tags['1.0'].commit.hexsha
        event = self.fake_gitlab.getGitTagEvent(
            'org/project', '1.0', tagsha)
        self.fake_gitlab.emitEvent(event)
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))
        self.assertEqual(
            'SUCCESS',
            self.getJobFromHistory('project-tag-job').result)
        job = self.getJobFromHistory('project-tag-job')
        zuulvars = job.parameters['zuul']
        self.assertEqual('refs/tags/1.0', zuulvars['ref'])
        self.assertEqual('tag', zuulvars['pipeline'])
        self.assertEqual('project-tag-job', zuulvars['job'])
        self.assertEqual(tagsha, zuulvars['newrev'])
        self.assertEqual(tagsha, zuulvars['commit_id'])

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_pull_request_with_dyn_reconf(self):
        path = os.path.join(self.upstream_root, 'org/project')
        zuul_yaml = [
            {'job': {
                'name': 'project-test3',
                'run': 'job.yaml'
            }},
            {'project': {
                'check': {
                    'jobs': [
                        'project-test3'
                    ]
                }
            }}
        ]
        playbook = "- hosts: all\n  tasks: []"

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project', 'master', 'A',
            base_sha=git.Repo(path).head.object.hexsha)
        A.addCommit(
            {'.zuul.yaml': yaml.dump(zuul_yaml),
             'job.yaml': playbook}
        )
        A.addCommit({"dummy.file": ""})
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test2').result)
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test3').result)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_pull_request_with_dyn_reconf_alt(self):
        with self.fake_gitlab.enable_uncomplete_mr():
            zuul_yaml = [
                {'job': {
                    'name': 'project-test3',
                    'run': 'job.yaml'
                }},
                {'project': {
                    'check': {
                        'jobs': [
                            'project-test3'
                        ]
                    }
                }}
            ]
            playbook = "- hosts: all\n  tasks: []"
            A = self.fake_gitlab.openFakeMergeRequest(
                'org/project', 'master', 'A')
            A.addCommit(
                {'.zuul.yaml': yaml.dump(zuul_yaml),
                 'job.yaml': playbook}
            )
            A.addCommit({"dummy.file": ""})
            self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
            self.waitUntilSettled()

            self.assertEqual('SUCCESS',
                             self.getJobFromHistory('project-test1').result)
            self.assertEqual('SUCCESS',
                             self.getJobFromHistory('project-test2').result)
            self.assertEqual('SUCCESS',
                             self.getJobFromHistory('project-test3').result)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_ref_updated_and_tenant_reconfigure(self):

        self.waitUntilSettled()
        old = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)

        zuul_yaml = [
            {'job': {
                'name': 'project-post-job2',
                'run': 'job.yaml'
            }},
            {'project': {
                'post': {
                    'jobs': [
                        'project-post-job2'
                    ]
                }
            }}
        ]
        playbook = "- hosts: all\n  tasks: []"
        self.create_commit(
            'org/project',
            {'.zuul.yaml': yaml.dump(zuul_yaml),
             'job.yaml': playbook},
            message='Add InRepo configuration'
        )
        event = self.fake_gitlab.getPushEvent('org/project',
                                              modified_files=['.zuul.yaml'])
        self.fake_gitlab.emitEvent(event)
        self.waitUntilSettled()

        new = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)
        # New timestamp should be greater than the old timestamp
        self.assertLess(old, new)

        self.assertHistory(
            [{'name': 'project-post-job'},
             {'name': 'project-post-job2'},
            ], ordered=False
        )

    @simple_layout('layouts/crd-gitlab.yaml', driver='gitlab')
    def test_crd_independent(self):

        # Create a change in project1 that a project2 change will depend on
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project1', 'master', 'A')

        # Create a commit in B that sets the dependency on A
        msg = "Depends-On: %s" % A.url
        B = self.fake_gitlab.openFakeMergeRequest(
            'org/project2', 'master', 'B', description=msg)

        # Make an event to re-use
        self.fake_gitlab.emitEvent(B.getMergeRequestOpenedEvent())
        self.waitUntilSettled()

        # The changes for the job from project2 should include the project1
        # MR content
        changes = self.getJobFromHistory(
            'project2-test', 'org/project2').changes

        self.assertEqual(changes, "%s,%s %s,%s" % (A.number,
                                                   A.sha,
                                                   B.number,
                                                   B.sha))

        # There should be no more changes in the queue
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        self.assertEqual(
            len(tenant.layout.pipeline_managers['check'].state.queues), 0)

    @simple_layout('layouts/requirements-gitlab.yaml', driver='gitlab')
    def test_state_require(self):

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project1', 'master', 'A')

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        # Close the MR
        A.closeMergeRequest()

        # A recheck will not trigger the job
        self.fake_gitlab.emitEvent(
            A.getMergeRequestCommentedEvent('recheck'))
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        # Merge the MR
        A.mergeMergeRequest()

        # A recheck will not trigger the job
        self.fake_gitlab.emitEvent(
            A.getMergeRequestCommentedEvent('recheck'))
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        # Re-open the MR
        A.reopenMergeRequest()

        # A recheck will trigger the job
        self.fake_gitlab.emitEvent(
            A.getMergeRequestCommentedEvent('recheck'))
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

    @simple_layout('layouts/requirements-gitlab.yaml', driver='gitlab')
    def test_approval_require(self):

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project2', 'master', 'A')

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        A.approved = True

        self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        A.approved = False

        self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

    @simple_layout('layouts/requirements-gitlab.yaml', driver='gitlab')
    def test_approval_require_community_edition(self):

        with self.fake_gitlab.enable_community_edition():
            A = self.fake_gitlab.openFakeMergeRequest(
                'org/project2', 'master', 'A')

            self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
            self.waitUntilSettled()
            self.assertEqual(0, len(self.history))

            A.approved = True

            self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
            self.waitUntilSettled()
            self.assertEqual(1, len(self.history))

            A.approved = False

            self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
            self.waitUntilSettled()
            self.assertEqual(1, len(self.history))

    @simple_layout('layouts/requirements-gitlab.yaml', driver='gitlab')
    def test_label_require(self):

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project3', 'master', 'A')

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        A.labels = ['gateit', 'prio:low']

        self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        A.labels = ['gateit', 'prio:low', 'another_label']

        self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

    @simple_layout('layouts/gitlab-label-add-remove.yaml', driver='gitlab')
    def test_label_add_remove(self):

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project1', 'master', 'A')
        A.labels = ['removeme1', 'removeme2']

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))
        self.assertEqual(set(A.labels), {'addme1', 'addme2'})

    @simple_layout('layouts/merging-gitlab.yaml', driver='gitlab')
    def test_merge_blocking_discussions(self):

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project2', 'master', 'A')

        A.blocking_discussions_resolved = False
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        # canMerge is not validated
        self.assertEqual(0, len(self.history))

        A.blocking_discussions_resolved = True
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        # canMerge is validated
        self.assertEqual(1, len(self.history))

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test').result)
        self.assertEqual('merged', A.state)

    @simple_layout('layouts/merging-gitlab.yaml', driver='gitlab')
    def test_merge_action_in_independent(self):

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project1', 'master', 'A')

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()

        self.assertEqual(1, len(self.history))
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test').result)
        self.assertEqual('merged', A.state)

    @simple_layout('layouts/merging-gitlab.yaml', driver='gitlab')
    def test_merge_action_in_dependent(self):

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project2', 'master', 'A')
        A.merge_status = 'cannot_be_merged'

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        # canMerge is not validated
        self.assertEqual(0, len(self.history))

        # Set Merge request can be merged
        A.merge_status = 'can_be_merged'
        self.fake_gitlab.emitEvent(A.getMergeRequestUpdatedEvent())
        self.waitUntilSettled()
        # canMerge is validated
        self.assertEqual(1, len(self.history))

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test').result)
        self.assertEqual('merged', A.state)

    @simple_layout('layouts/merging-gitlab-squash-merge.yaml', driver='gitlab')
    def test_merge_squash(self):

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project1', 'master', 'A')

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        # canMerge is validated
        self.assertEqual(1, len(self.history))

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test').result)
        self.assertEqual('merged', A.state)
        self.assertTrue(A.squash_merge)

    @simple_layout('layouts/crd-gitlab.yaml', driver='gitlab')
    def test_crd_dependent(self):

        # Create a change in project3 that a project4 change will depend on
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project3', 'master', 'A')
        A.approved = True

        # Create a change B that sets the dependency on A
        msg = "Depends-On: %s" % A.url
        B = self.fake_gitlab.openFakeMergeRequest(
            'org/project4', 'master', 'B', description=msg)

        # Emit B opened event
        event = B.getMergeRequestOpenedEvent()
        self.fake_gitlab.emitEvent(event)
        self.waitUntilSettled()

        # B cannot be merged (not approved)
        self.assertEqual(0, len(self.history))

        # Approve B
        B.approved = True
        # And send the event
        self.fake_gitlab.emitEvent(event)
        self.waitUntilSettled()

        # The changes for the job from project4 should include the project3
        # MR content
        changes = self.getJobFromHistory(
            'project4-test', 'org/project4').changes

        self.assertEqual(changes, "%s,%s %s,%s" % (A.number,
                                                   A.sha,
                                                   B.number,
                                                   B.sha))

        self.assertTrue(A.is_merged)
        self.assertTrue(B.is_merged)

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_timer_event(self):
        self.executor_server.hold_jobs_in_build = True
        self.commitConfigUpdate('org/common-config',
                                'layouts/timer-gitlab.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        time.sleep(2)
        self.waitUntilSettled()
        self.assertEqual(len(self.builds), 1)
        self.executor_server.hold_jobs_in_build = False
        # Stop queuing timer triggered jobs so that the assertions
        # below don't race against more jobs being queued.
        self.commitConfigUpdate('org/common-config',
                                'layouts/no-timer-gitlab.yaml')
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()
        # If APScheduler is in mid-event when we remove the job, we
        # can end up with one more event firing, so give it an extra
        # second to settle.
        time.sleep(1)
        self.waitUntilSettled()
        self.executor_server.release()
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='project-bitrot', result='SUCCESS',
                 ref='refs/heads/master'),
        ], ordered=False)

    @simple_layout('layouts/crd-gitlab.yaml', driver='gitlab')
    def test_api_token(self):
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        _, project = tenant.getProject('org/project1')

        project_git_url = self.fake_gitlab.real_getGitUrl(project)
        # cloneurl created from config 'server' should be used
        # without credentials
        self.assertEqual(f"{self.fake_gitlab._test_baseurl}/org/project1.git",
                         project_git_url)

    @simple_layout('layouts/crd-gitlab.yaml', driver='gitlab2')
    def test_api_token_cloneurl(self):
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        _, project = tenant.getProject('org/project1')

        project_git_url = self.fake_gitlab2.real_getGitUrl(project)
        # cloneurl from config file should be used as it defines token name and
        # secret
        self.assertEqual("http://myusername:2222@gitlab/org/project1.git",
                         project_git_url)

    @simple_layout('layouts/crd-gitlab.yaml', driver='gitlab3')
    def test_api_token_name_cloneurl(self):
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        _, project = tenant.getProject('org/project1')

        project_git_url = self.fake_gitlab3.real_getGitUrl(project)
        # cloneurl from config file should be used as it defines token name and
        # secret, even if token name and token secret are defined
        self.assertEqual("http://myusername:2222@gitlabthree/org/project1.git",
                         project_git_url)

    @simple_layout('layouts/crd-gitlab.yaml', driver='gitlab4')
    def test_api_token_name(self):
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        _, project = tenant.getProject('org/project1')

        project_git_url = self.fake_gitlab4.real_getGitUrl(project)
        # cloneurl is not set, generate one from token name, token secret and
        # server
        self.assertEqual("http://tokenname4:444@localhost:"
                         f"{self.fake_gitlab4._test_web_server.port}"
                         "/org/project1.git",
                         project_git_url)

    @simple_layout('layouts/crd-gitlab.yaml', driver='gitlab5')
    def test_api_token_name_cloneurl_server(self):
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        _, project = tenant.getProject('org/project1')

        project_git_url = self.fake_gitlab5.real_getGitUrl(project)
        # cloneurl defines a url, without credentials. As token name is
        # set, include token name and secret in cloneurl, 'server' is
        # overwritten
        self.assertEqual("http://tokenname5:555@gitlabfivvve/org/project1.git",
                         project_git_url)

    @simple_layout('layouts/files-gitlab.yaml', driver='gitlab')
    def test_changed_file_match_filter(self):
        path = os.path.join(self.upstream_root, 'org/project')
        base_sha = git.Repo(path).head.object.hexsha

        files = {'{:03d}.txt'.format(n): 'test' for n in range(300)}
        files["foobar-requires"] = "test"
        files["to-be-removed"] = "test"
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project', 'master', 'A', files=files, base_sha=base_sha)

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        # project-test1 and project-test2 should be run
        self.assertEqual(2, len(self.history))

    @simple_layout('layouts/files-gitlab.yaml', driver='gitlab')
    def test_changed_file_match_filter_refresh(self):
        # Test that a refresh of a MR doesn't overwrite the change
        # files list supplied by a zuul merger.
        self.hold_merge_jobs_in_queue = True
        path = os.path.join(self.upstream_root, 'org/project')
        base_sha = git.Repo(path).head.object.hexsha

        files = {}
        # This files causes project-test1 to run
        files["foobar-requires"] = "test"
        # File "to-be-removed" is not included, so -test2 should not run.
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project', 'master', 'A', files=files, base_sha=base_sha)

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()

        for x in self.merger_api.all():
            if x.job_type == 'fileschanges':
                self.merger_api.release(x)

        self.waitUntilSettled()
        self.fake_gitlab.emitEvent(A.getMergeRequestCommentedEvent(
            'test comment'))
        self.waitUntilSettled()
        self.hold_merge_jobs_in_queue = False
        self.merger_api.release()
        self.waitUntilSettled()
        self.assertHistory([
            dict(name='project-test1', result='SUCCESS'),
        ])

    @simple_layout('layouts/files-gitlab.yaml', driver='gitlab')
    def test_changed_and_reverted_file_not_match_filter(self):
        path = os.path.join(self.upstream_root, 'org/project')
        base_sha = git.Repo(path).head.object.hexsha

        files = {'{:03d}.txt'.format(n): 'test' for n in range(300)}
        files["foobar-requires"] = "test"
        files["to-be-removed"] = "test"
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project', 'master', 'A', files=files, base_sha=base_sha)
        A.addCommit(delete_files=['to-be-removed'])

        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()
        # Only project-test1 should be run, because the file to-be-removed
        # is reverted and not in changed files to trigger project-test2
        self.assertEqual(1, len(self.history))

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_update_change(self):
        # This tests the updateChange code path when no event is
        # present (ie, during a pipeline refresh).
        conn = self.scheds.first.sched.connections.connections['gitlab']
        conn.gl_client.get_mr_wait_factor = 0
        with self.fake_gitlab.enable_uncomplete_mr():
            A = self.fake_gitlab.openFakeMergeRequest(
                'org/project', 'master', 'A')
            change_key = ChangeKey(conn.connection_name, "org/project",
                                   "MergeRequest", str(A.number), A.sha)
            # diff_refs has not populated yet, so this call tests the
            # without-event and without-diff_refs path.
            change = conn.getChange(change_key)
            self.assertIsNone(change.commit_id, None)
            self.fake_gitlab.emitEvent(
                A.getMergeRequestOpenedEvent(), project='org/project')
            self.waitUntilSettled()
            # The above emits an event, so we should have populated
            # the change cache using the event info.  This tests the
            # with-event and without-diff_refs path.
            change = conn.getChange(change_key)
            self.assertEqual(change.commit_id, A.sha)

        # We don't test with event and with diff_refs here, since
        # having diff_refs supercedes using event data.  Also, any
        # other test in the class which does not set the uncomplete
        # flag will be testing that path.

        # Delete the change from the cache
        conn._change_cache.delete(change_key)
        # This will force the driver to fetch the change info without
        # an event.  This tests the without-event and with-diff_refs
        # path
        change = conn.getChange(change_key)
        self.assertEqual(change.commit_id, A.sha)


class TestGitlabUnprotectedBranches(ZuulTestCase):
    config_file = 'zuul-gitlab-driver.conf'
    tenant_config_file = 'config/unprotected-branches-gitlab/main.yaml'

    @skipIfMultiScheduler()
    # This test is failing with multiple schedulers depending on which
    # scheduler did the tenant reconfiguration first. As the
    # assertions are all done on the objects from scheduler-0 they
    # will fail if scheduler-1 did the reconfig first.
    # To make this work with multiple schedulers, we might want to wait
    # until all schedulers completed their tenant reconfiguration.
    def test_unprotected_branches(self):
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        layout = tenant.layout

        # project1 should have parsed master
        self.assertIn('project1-job', layout.jobs)

        # project2 should have no parsed branch
        self.assertNotIn('project2-job', layout.jobs)

        # now enable branch protection and trigger reload
        self.fake_gitlab.protectBranch('org', 'project2', 'master')
        pevent = self.fake_gitlab.getPushEvent(project='org/project2')
        self.fake_gitlab.emitEvent(pevent)
        self.waitUntilSettled()

        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        layout = tenant.layout

        # project1 and project2 should have parsed master now
        self.assertIn('project1-job', layout.jobs)
        self.assertIn('project2-job', layout.jobs)

    def test_filtered_branches_in_build(self):
        """
        Tests unprotected branches are filtered in builds if excluded
        """
        self.executor_server.keep_jobdir = True

        # Enable branch protection on org/project2@master
        self.create_branch('org/project2', 'feat-x')
        self.fake_gitlab.protectBranch('org', 'project2', 'master',
                                       protected=True)

        # Enable branch protection on org/project3@stable. We'll use a MR on
        # this branch as a depends-on to validate that the stable branch
        # which is not protected in org/project2 is not filtered out.
        self.create_branch('org/project3', 'stable')
        self.fake_gitlab.protectBranch('org', 'project3', 'stable',
                                       protected=True)

        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()

        A = self.fake_gitlab.openFakeMergeRequest('org/project3', 'stable',
                                                  'A')
        msg = "Depends-On: %s" % A.url
        B = self.fake_gitlab.openFakeMergeRequest('org/project2', 'master',
                                                  'B', description=msg)

        self.fake_gitlab.emitEvent(B.getMergeRequestOpenedEvent())
        self.waitUntilSettled()

        build = self.history[0]
        path = os.path.join(
            build.jobdir.src_root, 'gitlab', 'org/project2')
        build_repo = git.Repo(path)
        branches = [x.name for x in build_repo.branches]
        self.assertNotIn('feat-x', branches)

        self.assertHistory([
            dict(name='used-job', result='SUCCESS',
                 changes="%s,%s %s,%s" % (A.number, A.sha,
                                          B.number, B.sha)),
        ])

    def test_unfiltered_branches_in_build(self):
        """
        Tests unprotected branches are not filtered in builds if not excluded
        """
        self.executor_server.keep_jobdir = True

        # Enable branch protection on org/project1@master
        self.create_branch('org/project1', 'feat-x')
        self.fake_gitlab.protectBranch('org', 'project1', 'master',
                                       protected=True)
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()

        A = self.fake_gitlab.openFakeMergeRequest('org/project1', 'master',
                                                  'A')
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()

        build = self.history[0]
        path = os.path.join(
            build.jobdir.src_root, 'gitlab', 'org/project1')
        build_repo = git.Repo(path)
        branches = [x.name for x in build_repo.branches]
        self.assertIn('feat-x', branches)

        self.assertHistory([
            dict(name='project-test', result='SUCCESS',
                 changes="%s,%s" % (A.number, A.sha)),
        ])

    def test_unprotected_push(self):
        """Test that unprotected pushes don't cause tenant reconfigurations"""

        # Prepare repo with an initial commit
        A = self.fake_gitlab.openFakeMergeRequest('org/project2', 'master',
                                                  'A')

        zuul_yaml = [
            {'job': {
                'name': 'used-job2',
                'run': 'playbooks/used-job.yaml'
            }},
            {'project': {
                'check': {
                    'jobs': [
                        'used-job2'
                    ]
                }
            }}
        ]

        A.addCommit({'zuul.yaml': yaml.dump(zuul_yaml)})
        A.mergeMergeRequest()

        # Do a push on top of A
        pevent = self.fake_gitlab.getPushEvent(project='org/project2',
                                               before=A.sha,
                                               branch='refs/heads/master')

        # record previous tenant reconfiguration time, which may not be set
        old = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)
        self.waitUntilSettled()

        self.fake_gitlab.emitEvent(pevent)
        self.waitUntilSettled()
        new = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)

        # We don't expect a reconfiguration because the push was to an
        # unprotected branch
        self.assertEqual(old, new)

        # now enable branch protection and trigger the push event again
        self.fake_gitlab.protectBranch('org', 'project2', 'master')

        self.fake_gitlab.emitEvent(pevent)
        self.waitUntilSettled()
        new = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)

        # We now expect that zuul reconfigured itself
        self.assertLess(old, new)

    def test_protected_branch_delete(self):
        """Test that protected branch deletes trigger a tenant reconfig"""

        # Prepare repo with an initial commit and enable branch protection
        self.fake_gitlab.protectBranch('org', 'project2', 'master')
        self.fake_gitlab.emitEvent(
            self.fake_gitlab.getPushEvent(
                project='org/project2', branch='refs/heads/master'))

        A = self.fake_gitlab.openFakeMergeRequest('org/project2', 'master',
                                                  'A')
        A.mergeMergeRequest()

        # add a spare branch so that the project is not empty after master gets
        # deleted.
        self.create_branch('org/project2', 'feat-x')
        self.fake_gitlab.protectBranch('org', 'project2', 'feat-x',
                                       protected=False)
        self.fake_gitlab.emitEvent(
            self.fake_gitlab.getPushEvent(
                project='org/project2', branch='refs/heads/feat-x'))
        self.waitUntilSettled()

        # record previous tenant reconfiguration time, which may not be set
        old = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)
        self.waitUntilSettled()

        # Delete the branch
        self.fake_gitlab.deleteBranch('org', 'project2', 'master')

        pevent = self.fake_gitlab.getPushEvent(project='org/project2',
                                               before=A.sha,
                                               after='0' * 40,
                                               branch='refs/heads/master')

        self.fake_gitlab.emitEvent(pevent)
        self.waitUntilSettled()
        new = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)

        # We now expect that zuul reconfigured itself as we deleted a protected
        # branch
        self.assertLess(old, new)

    # This test verifies that a PR is considered in case it was created for
    # a branch just has been set to protected before a tenant reconfiguration
    # took place.
    def test_reconfigure_on_pr_to_new_protected_branch(self):
        self.create_branch('org/project2', 'release')
        self.create_branch('org/project2', 'feature')

        self.fake_gitlab.protectBranch('org', 'project2', 'master')
        self.fake_gitlab.protectBranch('org', 'project2', 'release',
                                       protected=False)
        self.fake_gitlab.protectBranch('org', 'project2', 'feature',
                                       protected=False)

        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))
        self.waitUntilSettled()

        self.fake_gitlab.protectBranch('org', 'project2', 'release')

        self.executor_server.hold_jobs_in_build = True

        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project2', 'release', 'A')
        self.fake_gitlab.emitEvent(A.getMergeRequestOpenedEvent())
        self.waitUntilSettled()

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('used-job').result)

        job = self.getJobFromHistory('used-job')
        zuulvars = job.parameters['zuul']
        self.assertEqual(str(A.number), zuulvars['change'])
        self.assertEqual(str(A.sha), zuulvars['patchset'])
        self.assertEqual('release', zuulvars['branch'])

        self.assertEqual(1, len(self.history))

    def _test_push_event_reconfigure(self, project, branch,
                                     expect_reconfigure=False,
                                     old_sha=None, new_sha=None,
                                     modified_files=None,
                                     removed_files=None):
        pevent = self.fake_gitlab.getPushEvent(
            project=project,
            branch='refs/heads/%s' % branch,
            before=old_sha,
            after=new_sha)

        # record previous tenant reconfiguration time, which may not be set
        old = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)
        self.waitUntilSettled()

        self.fake_gitlab.emitEvent(pevent)
        self.waitUntilSettled()
        new = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)

        if expect_reconfigure:
            # New timestamp should be greater than the old timestamp
            self.assertLess(old, new)
        else:
            # Timestamps should be equal as no reconfiguration shall happen
            self.assertEqual(old, new)

    def test_push_event_reconfigure_complex_branch(self):

        branch = 'feature/somefeature'
        project = 'org/project2'

        # prepare an existing branch
        self.create_branch(project, branch)

        self.fake_gitlab.protectBranch(*project.split('/'), branch,
                                       protected=False)

        self.fake_gitlab.emitEvent(
            self.fake_gitlab.getPushEvent(
                project,
                branch='refs/heads/%s' % branch))
        self.waitUntilSettled()

        A = self.fake_gitlab.openFakeMergeRequest(project, branch, 'A')
        old_sha = A.sha
        A.mergeMergeRequest()
        new_sha = random_sha1()

        # branch is not protected, no reconfiguration even if config file
        self._test_push_event_reconfigure(project, branch,
                                          expect_reconfigure=False,
                                          old_sha=old_sha,
                                          new_sha=new_sha,
                                          modified_files=['zuul.yaml'])

        # branch is not protected: no reconfiguration
        self.fake_gitlab.deleteBranch(*project.split('/'), branch)

        self._test_push_event_reconfigure(project, branch,
                                          expect_reconfigure=False,
                                          old_sha=new_sha,
                                          new_sha='0' * 40,
                                          removed_files=['zuul.yaml'])


class TestGitlabDriverNoPool(ZuulTestCase):
    config_file = 'zuul-gitlab-driver-no-pool.conf'

    @simple_layout('layouts/basic-gitlab.yaml', driver='gitlab')
    def test_merge_request_opened(self):

        description = "This is the\nMR description."
        A = self.fake_gitlab.openFakeMergeRequest(
            'org/project', 'master', 'A', description=description)
        self.fake_gitlab.emitEvent(
            A.getMergeRequestOpenedEvent(), project='org/project')
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test2').result)

        job = self.getJobFromHistory('project-test2')
        zuulvars = job.parameters['zuul']
        self.assertEqual(str(A.number), zuulvars['change'])
        self.assertEqual(str(A.sha), zuulvars['patchset'])
        self.assertEqual('master', zuulvars['branch'])
        self.assertEquals(f'{self.fake_gitlab._test_baseurl}/'
                          'org/project/merge_requests/1',
                          zuulvars['items'][0]['change_url'])
        self.assertEqual(zuulvars["message"], strings.b64encode(description))
        self.assertEqual(2, len(self.history))
        self.assertEqual(2, len(A.notes))
        self.assertEqual(
            A.notes[0]['body'], "Starting check jobs.")
        self.assertThat(
            A.notes[1]['body'],
            MatchesRegex(r'.*project-test1.*SUCCESS.*', re.DOTALL))
        self.assertThat(
            A.notes[1]['body'],
            MatchesRegex(r'.*project-test2.*SUCCESS.*', re.DOTALL))
        self.assertTrue(A.approved)
