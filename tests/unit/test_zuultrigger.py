# Copyright 2014 Hewlett-Packard Development Company, L.P.
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

from unittest import mock

from tests.base import ZuulTestCase, ZuulGithubAppTestCase
from zuul.driver.zuul.zuulmodel import ZuulTriggerEvent


class TestZuulTriggerParentChangeEnqueued(ZuulTestCase):
    tenant_config_file = 'config/zuultrigger/parent-change-enqueued/main.yaml'

    def test_zuul_trigger_parent_change_enqueued(self):
        "Test Zuul trigger event: parent-change-enqueued"
        # This test has the following three changes:
        # B1 -> A; B2 -> A
        # When A is enqueued in the gate, B1 and B2 should both attempt
        # to be enqueued in both pipelines.  B1 should end up in check
        # and B2 in gate because of differing pipeline requirements.
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        B1 = self.fake_gerrit.addFakeChange('org/project', 'master', 'B1')
        B2 = self.fake_gerrit.addFakeChange('org/project', 'master', 'B2')
        A.addApproval('Code-Review', 2)
        B1.addApproval('Code-Review', 2)
        B2.addApproval('Code-Review', 2)
        A.addApproval('Verified', 1, username="for-check")   # reqd by check
        A.addApproval('Verified', 1, username="for-gate")    # reqd by gate
        B1.addApproval('Verified', 1, username="for-check")  # go to check
        B2.addApproval('Verified', 1, username="for-gate")   # go to gate
        B1.addApproval('Approved', 1)
        B2.addApproval('Approved', 1)
        B1.setDependsOn(A, 1)
        B2.setDependsOn(A, 1)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        # Jobs are being held in build to make sure that 3,1 has time
        # to enqueue behind 1,1 so that the test is more
        # deterministic.
        self.waitUntilSettled()
        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual(len(self.history), 3)
        for job in self.history:
            if job.changes == '1,1':
                self.assertEqual(job.name, 'project-gate')
            elif job.changes == '1,1 2,1':
                self.assertEqual(job.name, 'project-check')
            elif job.changes == '1,1 3,1':
                self.assertEqual(job.name, 'project-gate')
            else:
                raise Exception("Unknown job")

        # Now directly enqueue a change into the check. As no pipeline reacts
        # on parent-change-enqueued from pipeline check no
        # parent-change-enqueued event is expected.
        _add_trigger_event = self.scheds.first.sched.addTriggerEvent

        def addTriggerEvent(driver_name, event):
            self.assertNotIsInstance(event, ZuulTriggerEvent)
            _add_trigger_event(driver_name, event)

        with mock.patch.object(
            self.scheds.first.sched, "addTriggerEvent", addTriggerEvent
        ):
            C = self.fake_gerrit.addFakeChange('org/project', 'master', 'C')
            C.addApproval('Verified', 1, username="for-check")
            D = self.fake_gerrit.addFakeChange('org/project', 'master', 'D')
            D.addApproval('Verified', 1, username="for-check")
            D.setDependsOn(C, 1)
            self.fake_gerrit.addEvent(C.getPatchsetCreatedEvent(1))

            self.waitUntilSettled()
            self.assertEqual(len(self.history), 4)


class TestZuulTriggerParentChangeEnqueuedGithub(ZuulGithubAppTestCase):
    tenant_config_file = \
        'config/zuultrigger/parent-change-enqueued-github/main.yaml'
    config_file = 'zuul-github-driver.conf'

    def test_zuul_trigger_parent_change_enqueued(self):
        "Test Zuul trigger event: parent-change-enqueued"
        # This test has the following three changes:
        # B1 -> A; B2 -> A
        # When A is enqueued in the gate, B1 and B2 should both attempt
        # to be enqueued in both pipelines.  B1 should end up in check
        # and B2 in gate because of differing pipeline requirements.
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_github.openFakePullRequest('org/project', 'master', 'A')
        msg = "Depends-On: https://github.com/org/project/pull/%s" % A.number
        B1 = self.fake_github.openFakePullRequest(
            'org/project', 'master', 'B1', body=msg)
        B2 = self.fake_github.openFakePullRequest(
            'org/project', 'master', 'B2', body=msg)
        A.addReview('derp', 'APPROVED')
        B1.addReview('derp', 'APPROVED')
        B2.addReview('derp', 'APPROVED')
        A.addLabel('for-gate')    # required by gate
        A.addLabel('for-check')   # required by check
        B1.addLabel('for-check')  # should go to check
        B2.addLabel('for-gate')   # should go to gate

        # In this case we have two installations
        # 1: org/common-config, org/project (used by tenant-one and tenant-two)
        # 2: org2/project (only used by tenant-two)
        # In order to track accesses to the installations enable client
        # recording in the fake github.
        self.fake_github.record_clients = True

        self.fake_github.emitEvent(A.getReviewAddedEvent('approved'))
        # Jobs are being held in build to make sure that 3,1 has time
        # to enqueue behind 1,1 so that the test is more
        # deterministic.
        self.waitUntilSettled()
        self.executor_server.hold_jobs_in_build = False
        self.executor_server.release()
        self.waitUntilSettled()

        self.assertEqual(len(self.history), 3)
        for job in self.history:
            if job.changes == '1,{}'.format(A.head_sha):
                self.assertEqual(job.name, 'project-gate')
            elif job.changes == '1,{} 2,{}'.format(A.head_sha, B1.head_sha):
                self.assertEqual(job.name, 'project-check')
            elif job.changes == '1,{} 3,{}'.format(A.head_sha, B2.head_sha):
                self.assertEqual(job.name, 'project-gate')
            else:
                raise Exception("Unknown job")

        # Now directly enqueue a change into the check. As no pipeline reacts
        # on parent-change-enqueued from pipeline check no
        # parent-change-enqueued event is expected.
        self.waitUntilSettled()

        _add_trigger_event = self.scheds.first.sched.addTriggerEvent

        def addTriggerEvent(driver_name, event):
            self.assertNotIsInstance(event, ZuulTriggerEvent)
            _add_trigger_event(driver_name, event)

        with mock.patch.object(
            self.scheds.first.sched, "addTriggerEvent", addTriggerEvent
        ):
            C = self.fake_github.openFakePullRequest(
                'org/project', 'master', 'C'
            )
            C.addLabel('for-check')  # should go to check

            msg = "Depends-On: https://github.com/org/project1/pull/{}".format(
                C.number
            )
            D = self.fake_github.openFakePullRequest(
                'org/project', 'master', 'D', body=msg)
            D.addLabel('for-check')  # should go to check
            self.fake_github.emitEvent(C.getPullRequestOpenedEvent())

            self.waitUntilSettled()
            self.assertEqual(len(self.history), 4)

        # After starting recording installation containing org2/project
        # should not be contacted
        gh_manager = self.fake_github._github_client_manager
        inst_id_to_check = gh_manager.installation_map['org2/project']
        inst_clients = [x for x in gh_manager.recorded_clients
                        if x._inst_id == inst_id_to_check]
        self.assertEqual(len(inst_clients), 0)


class TestZuulTriggerProjectChangeMerged(ZuulTestCase):

    tenant_config_file = 'config/zuultrigger/project-change-merged/main.yaml'

    def test_zuul_trigger_project_change_merged(self):
        # This test has the following three changes:
        # A, B, C;  B conflicts with A, but C does not.
        # When A is merged, B and C should be checked for conflicts,
        # and B should receive a -1.
        # D and E are used to repeat the test in the second part, but
        # are defined here to that they end up in the trigger cache.
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B')
        C = self.fake_gerrit.addFakeChange('org/project', 'master', 'C')
        D = self.fake_gerrit.addFakeChange('org/project', 'master', 'D')
        E = self.fake_gerrit.addFakeChange('org/project', 'master', 'E')
        A.addPatchset({'conflict': 'foo'})
        B.addPatchset({'conflict': 'bar'})
        D.addPatchset({'conflict2': 'foo'})
        E.addPatchset({'conflict2': 'bar'})
        A.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(A.addApproval('Approved', 1))
        self.waitUntilSettled()

        self.assertEqual(len(self.history), 1)
        self.assertEqual(self.history[0].name, 'project-gate')
        self.assertEqual(A.reported, 2)
        self.assertEqual(B.reported, 1)
        self.assertEqual(C.reported, 0)
        self.assertEqual(D.reported, 0)
        self.assertEqual(E.reported, 0)
        self.assertIn(
            "Merge Failed.\n\nThis change or one of its cross-repo "
            "dependencies was unable to be automatically merged with the "
            "current state of its repository. Please rebase the change and "
            "upload a new patchset.",
            B.messages[0])
        self.assertIn(
            'Error merging gerrit/org/project for 2,2',
            B.messages[0])

        self.assertTrue("project:{org/project} status:open" in
                        self.fake_gerrit.queries)

        # Ensure the gerrit driver has updated its cache after the
        # previous comments were left:
        self.fake_gerrit.addEvent(A.getChangeCommentEvent(2))
        self.fake_gerrit.addEvent(B.getChangeCommentEvent(2))
        self.waitUntilSettled()

        # Reconfigure and run the test again.  This is a regression
        # check to make sure that we don't end up with a stale trigger
        # cache that has references to projects from the old
        # configuration.
        self.scheds.execute(lambda app: app.sched.reconfigure(app.config))

        D.addApproval('Code-Review', 2)
        self.fake_gerrit.addEvent(D.addApproval('Approved', 1))
        self.waitUntilSettled()

        self.assertEqual(len(self.history), 2)
        self.assertEqual(self.history[1].name, 'project-gate')
        self.assertEqual(A.reported, 2)
        self.assertEqual(B.reported, 1)
        self.assertEqual(C.reported, 0)
        self.assertEqual(D.reported, 2)
        self.assertEqual(E.reported, 1)
        self.assertIn(
            "Merge Failed.\n\nThis change or one of its cross-repo "
            "dependencies was unable to be automatically merged with the "
            "current state of its repository. Please rebase the change and "
            "upload a new patchset.",
            E.messages[0])
        self.assertIn(
            'Error merging gerrit/org/project for 5,2',
            E.messages[0])
        self.assertIn("project:{org/project} status:open",
                      self.fake_gerrit.queries)
