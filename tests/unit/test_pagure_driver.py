# Copyright 2019 Red Hat
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

import os
import re
import git
import yaml
import socket

from testtools.matchers import MatchesRegex

from zuul.lib import strings
from zuul.zk.layout import LayoutState

from tests.base import ZuulTestCase, simple_layout
from tests.base import ZuulWebFixture

EMPTY_LAYOUT_STATE = LayoutState("", "", 0, None, {}, -1)


class TestPagureDriver(ZuulTestCase):
    config_file = 'zuul-pagure-driver.conf'

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_pull_request_opened(self):

        initial_comment = "This is the\nPR initial_comment."
        A = self.fake_pagure.openFakePullRequest(
            'org/project', 'master', 'A', initial_comment=initial_comment)
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test2').result)

        job = self.getJobFromHistory('project-test2')
        zuulvars = job.parameters['zuul']
        self.assertEqual(str(A.number), zuulvars['change'])
        self.assertEqual(str(A.commit_stop), zuulvars['patchset'])
        self.assertEqual(str(A.commit_stop), zuulvars['commit_id'])
        self.assertEqual('master', zuulvars['branch'])
        self.assertEquals('https://pagure/org/project/pull-request/1',
                          zuulvars['items'][0]['change_url'])
        self.assertEqual(zuulvars["message"],
                         strings.b64encode(initial_comment))
        self.assertEqual(2, len(self.history))
        self.assertEqual(2, len(A.comments))
        self.assertEqual(
            A.comments[0]['comment'], "Starting check jobs.")
        self.assertThat(
            A.comments[1]['comment'],
            MatchesRegex(r'.*\[project-test1 \]\(.*\).*', re.DOTALL))
        self.assertThat(
            A.comments[1]['comment'],
            MatchesRegex(r'.*\[project-test2 \]\(.*\).*', re.DOTALL))
        self.assertEqual(1, len(A.flags))
        self.assertEqual('success', A.flags[0]['status'])

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_pull_request_updated(self):

        A = self.fake_pagure.openFakePullRequest('org/project', 'master', 'A')
        pr_tip1 = A.commit_stop
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))
        self.assertHistory(
            [
                {'name': 'project-test1', 'changes': '1,%s' % pr_tip1},
                {'name': 'project-test2', 'changes': '1,%s' % pr_tip1},
            ], ordered=False
        )

        self.fake_pagure.emitEvent(A.getPullRequestUpdatedEvent())
        pr_tip2 = A.commit_stop
        self.waitUntilSettled()
        self.assertEqual(4, len(self.history))
        self.assertHistory(
            [
                {'name': 'project-test1', 'changes': '1,%s' % pr_tip1},
                {'name': 'project-test2', 'changes': '1,%s' % pr_tip1},
                {'name': 'project-test1', 'changes': '1,%s' % pr_tip2},
                {'name': 'project-test2', 'changes': '1,%s' % pr_tip2}
            ], ordered=False
        )

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_pull_request_updated_builds_aborted(self):

        A = self.fake_pagure.openFakePullRequest('org/project', 'master', 'A')
        pr_tip1 = A.commit_stop

        self.executor_server.hold_jobs_in_build = True

        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        self.fake_pagure.emitEvent(A.getPullRequestUpdatedEvent())
        pr_tip2 = A.commit_stop
        self.waitUntilSettled()

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertHistory(
            [
                {'name': 'project-test1', 'result': 'ABORTED',
                 'changes': '1,%s' % pr_tip1},
                {'name': 'project-test2', 'result': 'ABORTED',
                 'changes': '1,%s' % pr_tip1},
                {'name': 'project-test1', 'changes': '1,%s' % pr_tip2},
                {'name': 'project-test2', 'changes': '1,%s' % pr_tip2}
            ], ordered=False
        )

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_pull_request_commented(self):

        A = self.fake_pagure.openFakePullRequest('org/project', 'master', 'A')
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent('I like that change'))
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent('recheck'))
        self.waitUntilSettled()
        self.assertEqual(4, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestInitialCommentEvent('Initial comment edited'))
        self.waitUntilSettled()
        self.assertEqual(6, len(self.history))

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_pull_request_with_dyn_reconf(self):

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

        A = self.fake_pagure.openFakePullRequest(
            'org/project', 'master', 'A')
        A.addCommit(
            {'.zuul.yaml': yaml.dump(zuul_yaml),
             'job.yaml': playbook}
        )
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test2').result)
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test3').result)

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_ref_updated(self):

        event = self.fake_pagure.getGitReceiveEvent('org/project')
        expected_newrev = event[1]['msg']['end_commit']
        expected_oldrev = event[1]['msg']['old_commit']
        self.fake_pagure.emitEvent(event)
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
            'https://pagure/org/project/c/%s' % zuulvars['newrev'],
            zuulvars['change_url'])
        self.assertEqual(expected_newrev, zuulvars['newrev'])
        self.assertEqual(expected_oldrev, zuulvars['oldrev'])
        self.assertEqual(expected_newrev, zuulvars['commit_id'])

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_ref_created(self):

        self.create_branch('org/project', 'stable-1.0')
        path = os.path.join(self.upstream_root, 'org/project')
        repo = git.Repo(path)
        newrev = repo.commit('refs/heads/stable-1.0').hexsha
        event = self.fake_pagure.getGitBranchEvent(
            'org/project', 'stable-1.0', 'creation', newrev)
        old = self.scheds.first.sched.tenant_layout_state.get(
            'tenant-one', EMPTY_LAYOUT_STATE)
        self.fake_pagure.emitEvent(event)
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

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_ref_deleted(self):

        event = self.fake_pagure.getGitBranchEvent(
            'org/project', 'stable-1.0', 'deletion', '0' * 40)
        self.fake_pagure.emitEvent(event)
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
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
        event = self.fake_pagure.getGitReceiveEvent('org/project')
        self.fake_pagure.emitEvent(event)
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

    @simple_layout('layouts/files-pagure.yaml', driver='pagure')
    def test_pull_matched_file_event(self):
        A = self.fake_pagure.openFakePullRequest(
            'org/project', 'master', 'A',
            files={'random.txt': 'test', 'build-requires': 'test'})
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        B = self.fake_pagure.openFakePullRequest('org/project', 'master', 'B',
                                                 files={'random.txt': 'test2'})
        self.fake_pagure.emitEvent(B.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        C = self.fake_pagure.openFakePullRequest(
            'org/project', 'master', 'C',
            files={'build-requires': 'test'})
        self.fake_pagure.emitEvent(C.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_tag_created(self):

        path = os.path.join(self.upstream_root, 'org/project')
        repo = git.Repo(path)
        repo.create_tag('1.0')
        tagsha = repo.tags['1.0'].commit.hexsha
        event = self.fake_pagure.getGitTagCreatedEvent(
            'org/project', '1.0', tagsha)
        self.fake_pagure.emitEvent(event)
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

    @simple_layout('layouts/requirements-pagure.yaml', driver='pagure')
    def test_pr_score_require_1_vote(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project1', 'master', 'A')
        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent("I like that change"))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsup:"))
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        self.assertEqual(
            'SUCCESS',
            self.getJobFromHistory('project-test').result)

    @simple_layout('layouts/requirements-pagure.yaml', driver='pagure')
    def test_pr_score_require_2_votes(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project2', 'master', 'A')
        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent("I like that change"))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsup:"))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsdown:"))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsup:"))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsup:"))
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

    @simple_layout('layouts/requirements-pagure.yaml', driver='pagure')
    def test_status_trigger(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project3', 'master', 'A')

        self.fake_pagure.emitEvent(
            A.getPullRequestStatusSetEvent("failure"))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestStatusSetEvent("success"))
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

    @simple_layout('layouts/requirements-pagure.yaml', driver='pagure')
    def test_tag_trigger(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project4', 'master', 'A')

        self.fake_pagure.emitEvent(
            A.getPullRequestTagAddedEvent(["lambda"]))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestTagAddedEvent(["gateit", "lambda"]))
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        self.fake_pagure.emitEvent(
            A.getPullRequestTagAddedEvent(["mergeit"]))
        self.waitUntilSettled()
        self.assertEqual(2, len(self.history))

    @simple_layout('layouts/requirements-pagure.yaml', driver='pagure')
    def test_tag_require(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project5', 'master', 'A')

        self.fake_pagure.emitEvent(A.getPullRequestUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        A.tags = ["lambda"]
        self.fake_pagure.emitEvent(A.getPullRequestUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        A.tags = ["lambda", "gateit"]
        self.fake_pagure.emitEvent(A.getPullRequestUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

        A.tags = []
        self.fake_pagure.emitEvent(A.getPullRequestUpdatedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

    @simple_layout('layouts/requirements-pagure.yaml', driver='pagure')
    def test_flag_require(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project7', 'master', 'A')

        # CI status from other CIs must not be handled
        self.fake_pagure.emitEvent(
            A.getPullRequestStatusSetEvent("success", username="notzuul"))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))
        self.assertEqual(1, len(A.flags))

        self.fake_pagure.emitEvent(
            A.getPullRequestStatusSetEvent("failure"))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))
        self.assertEqual(2, len(A.flags))

        self.fake_pagure.emitEvent(
            A.getPullRequestStatusSetEvent("success"))
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))
        self.assertEqual(2, len(A.flags))

    @simple_layout('layouts/requirements-pagure.yaml', driver='pagure')
    def test_pull_request_closed(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project6', 'master', 'A')

        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        # Validate a closed but not merged PR does not trigger the pipeline
        self.fake_pagure.emitEvent(A.getPullRequestClosedEvent(merged=False))
        self.waitUntilSettled()
        self.assertEqual(0, len(self.history))

        # Reset the status to Open
        # Validate a closed and merged PR triggers the pipeline
        A.status = 'Open'
        A.is_merged = False
        self.fake_pagure.emitEvent(A.getPullRequestClosedEvent())
        self.waitUntilSettled()
        self.assertEqual(1, len(self.history))

    @simple_layout('layouts/merging-pagure.yaml', driver='pagure')
    def test_merge_action_in_independent(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project1', 'master', 'A')
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()

        self.assertEqual(1, len(self.history))
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test').result)
        self.assertEqual('Merged', A.status)

    @simple_layout('layouts/merging-pagure.yaml', driver='pagure')
    def test_merge_action_in_dependent(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project2', 'master', 'A')
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        # connection.canMerge is not validated
        self.assertEqual(0, len(self.history))

        # Set the mergeable PR flag to a expected value
        A.cached_merge_status = 'MERGE'
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        # connection.canMerge is not validated
        self.assertEqual(0, len(self.history))

        # Set the score threshold as reached
        # Here we use None that means no specific score is required
        A.threshold_reached = None
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        # connection.canMerge is not validated
        self.assertEqual(0, len(self.history))

        # Set CI flag as passed CI
        A.addFlag('success', 'https://url', 'Build passed')
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        # connection.canMerge is validated
        self.assertEqual(1, len(self.history))

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test').result)
        self.assertEqual('Merged', A.status)

    @simple_layout('layouts/crd-pagure.yaml', driver='pagure')
    def test_crd_independent(self):

        # Create a change in project1 that a project2 change will depend on
        A = self.fake_pagure.openFakePullRequest('org/project1', 'master', 'A')

        # Create a commit in B that sets the dependency on A
        msg = "Depends-On: %s" % A.url
        B = self.fake_pagure.openFakePullRequest(
            'org/project2', 'master', 'B', initial_comment=msg)

        # Make an event to re-use
        event = B.getPullRequestCommentedEvent('A comment')
        self.fake_pagure.emitEvent(event)
        self.waitUntilSettled()

        # The changes for the job from project2 should include the project1
        # PR content
        changes = self.getJobFromHistory(
            'project2-test', 'org/project2').changes

        self.assertEqual(changes, "%s,%s %s,%s" % (A.number,
                                                   A.commit_stop,
                                                   B.number,
                                                   B.commit_stop))

        # There should be no more changes in the queue
        tenant = self.scheds.first.sched.abide.tenants.get('tenant-one')
        self.assertEqual(len(
            tenant.layout.pipeline_managers['check'].state.queues), 0)

    @simple_layout('layouts/crd-pagure.yaml', driver='pagure')
    def test_crd_dependent(self):

        # Create a change in project3 that a project4 change will depend on
        A = self.fake_pagure.openFakePullRequest('org/project3', 'master', 'A')

        # Create a commit in B that sets the dependency on A
        msg = "Depends-On: %s" % A.url
        B = self.fake_pagure.openFakePullRequest(
            'org/project4', 'master', 'B', initial_comment=msg)

        # Make an event to re-use
        event = B.getPullRequestCommentedEvent('A comment')

        self.fake_pagure.emitEvent(event)
        self.waitUntilSettled()

        # Neither A and B can't merge (no flag, no score threshold)
        self.assertEqual(0, len(self.history))

        B.threshold_reached = True
        B.addFlag('success', 'https://url', 'Build passed')
        self.fake_pagure.emitEvent(event)
        self.waitUntilSettled()

        # B can't merge as A got no flag, no score threshold
        self.assertEqual(0, len(self.history))

        A.threshold_reached = True
        A.addFlag('success', 'https://url', 'Build passed')
        self.fake_pagure.emitEvent(event)
        self.waitUntilSettled()

        # The changes for the job from project4 should include the project3
        # PR content
        changes = self.getJobFromHistory(
            'project4-test', 'org/project4').changes

        self.assertEqual(changes, "%s,%s %s,%s" % (A.number,
                                                   A.commit_stop,
                                                   B.number,
                                                   B.commit_stop))

        self.assertTrue(A.is_merged)
        self.assertTrue(B.is_merged)

    @simple_layout('layouts/crd-pagure.yaml', driver='pagure')
    def test_crd_needed_changes(self):

        # Given change A and B, where B depends on A, when A
        # completes B should be enqueued (using a shared queue)

        # Create a change in project3 that a project4 change will depend on
        A = self.fake_pagure.openFakePullRequest('org/project3', 'master', 'A')
        A.threshold_reached = True
        A.addFlag('success', 'https://url', 'Build passed')

        # Set B to depend on A
        msg = "Depends-On: %s" % A.url
        B = self.fake_pagure.openFakePullRequest(
            'org/project4', 'master', 'B', initial_comment=msg)
        # Make the driver aware of change B by sending an event
        # At that moment B can't merge
        self.fake_pagure.emitEvent(B.getPullRequestCommentedEvent('A comment'))
        # Now set B mergeable
        B.threshold_reached = True
        B.addFlag('success', 'https://url', 'Build passed')

        # Enqueue A, which will make the scheduler detect that B is
        # depending on so B will be enqueue as well.
        self.fake_pagure.emitEvent(A.getPullRequestCommentedEvent('A comment'))
        self.waitUntilSettled()

        # The changes for the job from project4 should include the project3
        # PR content
        changes = self.getJobFromHistory(
            'project4-test', 'org/project4').changes

        self.assertEqual(changes, "%s,%s %s,%s" % (A.number,
                                                   A.commit_stop,
                                                   B.number,
                                                   B.commit_stop))

        self.assertTrue(A.is_merged)
        self.assertTrue(B.is_merged)

    @simple_layout('layouts/files-pagure.yaml', driver='pagure')
    def test_changed_file_match_filter(self):
        files = {'{:03d}.txt'.format(n): 'test' for n in range(300)}
        files["foobar-requires"] = "test"
        files["to-be-removed"] = "test"
        A = self.fake_pagure.openFakePullRequest(
            'org/project', 'master', 'A', files=files)

        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        # project-test1 and project-test2 should be run
        self.assertEqual(2, len(self.history))

    @simple_layout('layouts/files-pagure.yaml', driver='pagure')
    def test_changed_and_reverted_file_not_match_filter(self):
        files = {'{:03d}.txt'.format(n): 'test' for n in range(3)}
        files["foobar-requires"] = "test"
        files["to-be-removed"] = "test"
        A = self.fake_pagure.openFakePullRequest(
            'org/project', 'master', 'A', files=files)
        A.addCommit(delete_files=['to-be-removed'])

        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent())
        self.waitUntilSettled()
        # Only project-test1 should be run, because the file to-be-removed
        # is reverted and not in changed files to trigger project-test2
        self.assertEqual(1, len(self.history))


class TestPagureToGerritCRD(ZuulTestCase):
    config_file = 'zuul-crd-pagure.conf'
    tenant_config_file = 'config/cross-source-pagure/gerrit.yaml'

    def test_crd_gate(self):
        "Test cross-repo dependencies"
        A = self.fake_pagure.openFakePullRequest('pagure/project2', 'master',
                                                 'A')
        B = self.fake_gerrit.addFakeChange('gerrit/project1', 'master', 'B')

        # A Depends-On: B
        A.editInitialComment('Depends-On: %s\n' % (B.data['url']))

        A.addFlag('success', 'https://url', 'Build passed')
        A.threshold_reached = True

        B.addApproval('Code-Review', 2)

        # Make A enter the pipeline
        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsup:"))
        self.waitUntilSettled()

        # Expect not merged as B not approved yet
        self.assertFalse(A.is_merged)
        self.assertEqual(B.data['status'], 'NEW')

        for connection in self.scheds.first.connections.connections.values():
            connection.maintainCache([], max_age=0)

        B.addApproval('Approved', 1)
        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsup:"))
        self.waitUntilSettled()

        self.assertTrue(A.is_merged)
        self.assertEqual(B.data['status'], 'MERGED')
        self.assertEqual(len(A.comments), 4)
        self.assertEqual(B.reported, 2)

        changes = self.getJobFromHistory(
            'project-merge', 'pagure/project2').changes
        self.assertEqual(changes, '1,1 1,%s' % A.commit_stop)

    def test_crd_check(self):
        "Test cross-repo dependencies in independent pipelines"
        A = self.fake_pagure.openFakePullRequest('pagure/project2', 'master',
                                                 'A')
        B = self.fake_gerrit.addFakeChange(
            'gerrit/project1', 'master', 'B')

        # A Depends-On: B
        A.editInitialComment('Depends-On: %s\n' % (B.data['url'],))

        self.executor_server.hold_jobs_in_build = True

        self.fake_pagure.emitEvent(A.getPullRequestUpdatedEvent())
        self.waitUntilSettled()

        self.assertTrue(self.builds[0].hasChanges(A, B))

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertFalse(A.is_merged)
        self.assertEqual(B.data['status'], 'NEW')
        self.assertEqual(len(A.comments), 2)
        self.assertEqual(B.reported, 0)

        changes = self.getJobFromHistory(
            'project-merge', 'pagure/project2').changes
        self.assertEqual(changes, '1,1 1,%s' % A.commit_stop)


class TestGerritToPagureCRD(ZuulTestCase):
    config_file = 'zuul-crd-pagure.conf'
    tenant_config_file = 'config/cross-source-pagure/gerrit.yaml'

    def test_crd_gate(self):
        "Test cross-repo dependencies"
        A = self.fake_gerrit.addFakeChange('gerrit/project1', 'master', 'A')
        B = self.fake_pagure.openFakePullRequest('pagure/project2', 'master',
                                                 'B')

        A.addApproval('Code-Review', 2)

        AM2 = self.fake_gerrit.addFakeChange('gerrit/project1', 'master',
                                             'AM2')
        AM1 = self.fake_gerrit.addFakeChange('gerrit/project1', 'master',
                                             'AM1')
        AM2.setMerged()
        AM1.setMerged()

        # A -> AM1 -> AM2
        # A Depends-On: B
        # M2 is here to make sure it is never queried.  If it is, it
        # means zuul is walking down the entire history of merged
        # changes.

        A.setDependsOn(AM1, 1)
        AM1.setDependsOn(AM2, 1)

        A.data['commitMessage'] = '%s\n\nDepends-On: %s\n' % (
            A.subject, B.url)

        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        self.assertEqual(A.data['status'], 'NEW')
        self.assertFalse(B.is_merged)

        for connection in self.scheds.first.connections.connections.values():
            connection.maintainCache([], max_age=0)

        B.addFlag('success', 'https://url', 'Build passed')
        B.threshold_reached = True
        self.fake_pagure.emitEvent(
            B.getPullRequestCommentedEvent(":thumbsup:"))
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))

        self.waitUntilSettled()

        self.assertEqual(AM2.queried, 0)
        self.assertEqual(A.data['status'], 'MERGED')
        self.assertTrue(B.is_merged)
        self.assertEqual(A.reported, 2)
        self.assertEqual(len(B.comments), 3)

        changes = self.getJobFromHistory(
            'project-merge', 'gerrit/project1').changes
        self.assertEqual(changes, '1,%s 1,1' % B.commit_stop)

    def test_crd_check(self):
        "Test cross-repo dependencies in independent pipelines"
        A = self.fake_gerrit.addFakeChange('gerrit/project1', 'master', 'A')
        B = self.fake_pagure.openFakePullRequest(
            'pagure/project2', 'master', 'B')

        # A Depends-On: B
        A.data['commitMessage'] = '%s\n\nDepends-On: %s\n' % (
            A.subject, B.url)

        self.executor_server.hold_jobs_in_build = True

        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        self.assertTrue(self.builds[0].hasChanges(A, B))

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual(A.data['status'], 'NEW')
        self.assertFalse(B.is_merged)
        self.assertEqual(A.reported, 1)
        self.assertEqual(len(B.comments), 0)

        changes = self.getJobFromHistory(
            'project-merge', 'gerrit/project1').changes
        self.assertEqual(changes, '1,%s 1,1' % B.commit_stop)


class TestPagureToGithubCRD(ZuulTestCase):
    config_file = 'zuul-crd-pagure.conf'
    tenant_config_file = 'config/cross-source-pagure/github.yaml'

    def test_crd_gate(self):
        "Test cross-repo dependencies"
        A = self.fake_pagure.openFakePullRequest('pagure/project2', 'master',
                                                 'A')
        B = self.fake_github.openFakePullRequest('github/project1', 'master',
                                                 'B')
        # A Depends-On: B
        A.editInitialComment('Depends-On: %s\n' % (B.url))

        A.addFlag('success', 'https://url', 'Build passed')
        A.threshold_reached = True

        # Make A enter the pipeline
        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsup:"))
        self.waitUntilSettled()

        # Expect not merged as B not approved yet
        self.assertFalse(A.is_merged)
        self.assertFalse(B.is_merged)

        for connection in self.scheds.first.connections.connections.values():
            connection.maintainCache([], max_age=0)

        B.addLabel('approved')
        self.fake_pagure.emitEvent(
            A.getPullRequestCommentedEvent(":thumbsup:"))
        self.waitUntilSettled()

        self.assertTrue(A.is_merged)
        self.assertTrue(B.is_merged)
        self.assertEqual(len(A.comments), 4)
        self.assertEqual(len(B.comments), 2)

        changes = self.getJobFromHistory(
            'project-merge', 'pagure/project2').changes
        self.assertEqual(changes, '1,%s 1,%s' % (B.head_sha, A.commit_stop))

    def test_crd_check(self):
        "Test cross-repo dependencies in independent pipelines"
        A = self.fake_pagure.openFakePullRequest('pagure/project2', 'master',
                                                 'A')
        B = self.fake_github.openFakePullRequest('github/project1', 'master',
                                                 'A')

        # A Depends-On: B
        A.editInitialComment('Depends-On: %s\n' % B.url)

        self.executor_server.hold_jobs_in_build = True

        self.fake_pagure.emitEvent(A.getPullRequestUpdatedEvent())
        self.waitUntilSettled()

        self.assertTrue(self.builds[0].hasChanges(A, B))

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertFalse(A.is_merged)
        self.assertFalse(B.is_merged)
        self.assertEqual(len(A.comments), 2)
        self.assertEqual(len(A.comments), 2)

        changes = self.getJobFromHistory(
            'project-merge', 'pagure/project2').changes
        self.assertEqual(changes, '1,%s 1,%s' % (B.head_sha, A.commit_stop))


class TestGithubToPagureCRD(ZuulTestCase):
    config_file = 'zuul-crd-pagure.conf'
    tenant_config_file = 'config/cross-source-pagure/github.yaml'

    # Those tests are also using the fake github implementation which
    # means that every scheduler gets a different fake github instance.
    # Thus, assertions might fail depending on which scheduler did the
    # interaction with Github.
    scheduler_count = 1

    def test_crd_gate(self):
        "Test cross-repo dependencies"
        A = self.fake_github.openFakePullRequest('github/project1', 'master',
                                                 'A')
        B = self.fake_pagure.openFakePullRequest('pagure/project2', 'master',
                                                 'B')

        # A Depends-On: B
        A.editBody('Depends-On: %s\n' % B.url)

        event = A.addLabel('approved')
        self.fake_github.emitEvent(event)
        self.waitUntilSettled()

        self.assertFalse(A.is_merged)
        self.assertFalse(B.is_merged)

        for connection in self.scheds.first.connections.connections.values():
            connection.maintainCache([], max_age=0)

        B.addFlag('success', 'https://url', 'Build passed')
        B.threshold_reached = True
        self.fake_pagure.emitEvent(
            B.getPullRequestCommentedEvent(":thumbsup:"))

        self.fake_github.emitEvent(event)

        self.waitUntilSettled()

        self.assertTrue(A.is_merged)
        self.assertTrue(B.is_merged)
        self.assertEqual(len(A.comments), 2)
        self.assertEqual(len(B.comments), 3)

        changes = self.getJobFromHistory(
            'project-merge', 'github/project1').changes
        self.assertEqual(changes, '1,%s 1,%s' % (B.commit_stop, A.head_sha))

    def test_crd_check(self):
        "Test cross-repo dependencies in independent pipelines"
        A = self.fake_github.openFakePullRequest(
            'github/project1', 'master', 'A')
        B = self.fake_pagure.openFakePullRequest(
            'pagure/project2', 'master', 'B')

        # A Depends-On: B
        self.executor_server.hold_jobs_in_build = True
        self.fake_github.emitEvent(A.editBody('Depends-On: %s\n' % B.url))
        self.waitUntilSettled()

        self.assertTrue(self.builds[0].hasChanges(A, B))

        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertFalse(A.is_merged)
        self.assertFalse(B.is_merged)
        self.assertEqual(len(A.comments), 1)
        self.assertEqual(len(B.comments), 0)

        changes = self.getJobFromHistory(
            'project-merge', 'github/project1').changes
        self.assertEqual(changes, '1,%s 1,%s' % (B.commit_stop, A.head_sha))


class TestPagureWebhook(ZuulTestCase):
    config_file = 'zuul-pagure-driver.conf'

    def setUp(self):
        super(TestPagureWebhook, self).setUp()
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

        self.fake_pagure.setZuulWebPort(port)

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_webhook(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project', 'master', 'A')
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent(),
                                   use_zuulweb=True,
                                   project='org/project',
                                   wrong_token=True)
        self.waitUntilSettled()
        self.assertEqual(len(self.history), 0)

        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent(),
                                   use_zuulweb=True,
                                   project='org/project')
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test2').result)


class TestPagureWebhookWhitelist(ZuulTestCase):
    config_file = 'zuul-pagure-driver-whitelist.conf'

    def setUp(self):
        super(TestPagureWebhookWhitelist, self).setUp()
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

        self.fake_pagure.setZuulWebPort(port)

    @simple_layout('layouts/basic-pagure.yaml', driver='pagure')
    def test_webhook_whitelist(self):

        A = self.fake_pagure.openFakePullRequest(
            'org/project', 'master', 'A')
        self.fake_pagure.emitEvent(A.getPullRequestOpenedEvent(),
                                   use_zuulweb=True,
                                   project='org/project',
                                   wrong_token=True)
        self.waitUntilSettled()

        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test1').result)
        self.assertEqual('SUCCESS',
                         self.getJobFromHistory('project-test2').result)
