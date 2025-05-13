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

from tests.base import (
    ZuulTestCase,
    simple_layout,
)


class TestSupercedent(ZuulTestCase):
    tenant_config_file = 'config/single-tenant/main.yaml'

    @simple_layout('layouts/supercedent.yaml')
    def test_supercedent(self):
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        arev = A.patchsets[-1]['revision']
        A.setMerged()
        self.fake_gerrit.addEvent(A.getRefUpdatedEvent())
        self.waitUntilSettled()

        # We should never run jobs for more than one change at a time
        self.assertEqual(len(self.builds), 1)

        # This change should be superceded by the next
        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B')
        B.setMerged()
        self.fake_gerrit.addEvent(B.getRefUpdatedEvent())
        self.waitUntilSettled()

        self.assertEqual(len(self.builds), 1)

        C = self.fake_gerrit.addFakeChange('org/project', 'master', 'C')
        crev = C.patchsets[-1]['revision']
        C.setMerged()
        self.fake_gerrit.addEvent(C.getRefUpdatedEvent())
        self.waitUntilSettled()

        self.assertEqual(len(self.builds), 1)

        self.executor_server.hold_jobs_in_build = True
        self.orderedRelease()
        self.assertHistory([
            dict(name='post-job', result='SUCCESS', newrev=arev),
            dict(name='post-job', result='SUCCESS', newrev=crev),
        ], ordered=False)

    @simple_layout('layouts/supercedent.yaml')
    def test_supercedent_branches(self):
        self.executor_server.hold_jobs_in_build = True
        self.create_branch('org/project', 'stable')
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        arev = A.patchsets[-1]['revision']
        A.setMerged()
        self.fake_gerrit.addEvent(A.getRefUpdatedEvent())
        self.waitUntilSettled()

        self.assertEqual(len(self.builds), 1)

        # This change should not be superceded
        B = self.fake_gerrit.addFakeChange('org/project', 'stable', 'B')
        brev = B.patchsets[-1]['revision']
        B.setMerged()
        self.fake_gerrit.addEvent(B.getRefUpdatedEvent())
        self.waitUntilSettled()

        self.assertEqual(len(self.builds), 2)

        self.executor_server.hold_jobs_in_build = True
        self.orderedRelease()
        self.assertHistory([
            dict(name='post-job', result='SUCCESS', newrev=arev),
            dict(name='post-job', result='SUCCESS', newrev=brev),
        ], ordered=False)

    @simple_layout('layouts/supercedent-promote.yaml')
    def test_supercedent_promote(self):
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_gerrit.addFakeChange('org/project', 'master', 'A')
        A.setMerged()
        self.fake_gerrit.addEvent(A.getChangeMergedEvent())
        self.waitUntilSettled()

        # We should never run jobs for more than one change at a time
        self.assertEqual(len(self.builds), 1)

        # This change should be superceded by the next
        B = self.fake_gerrit.addFakeChange('org/project', 'master', 'B')
        B.setMerged()
        self.fake_gerrit.addEvent(B.getChangeMergedEvent())
        self.waitUntilSettled()

        self.assertEqual(len(self.builds), 1)

        C = self.fake_gerrit.addFakeChange('org/project', 'master', 'C')
        C.setMerged()
        self.fake_gerrit.addEvent(C.getChangeMergedEvent())
        self.waitUntilSettled()

        self.assertEqual(len(self.builds), 1)

        self.executor_server.hold_jobs_in_build = True
        self.orderedRelease()
        self.assertHistory([
            dict(name='promote-job', result='SUCCESS', changes='1,1'),
            dict(name='promote-job', result='SUCCESS', changes='3,1'),
        ], ordered=False)


class TestSupercedentCircularDependencies(ZuulTestCase):
    config_file = "zuul-gerrit-github.conf"
    tenant_config_file = "config/circular-dependencies/main.yaml"

    @simple_layout('layouts/supercedent-circular-gerrit.yaml')
    def test_supercedent_gerrit_circular_deps(self):
        # Unlike other supercedent tests, this one operates on
        # pre-merge changes instead of post-merge refs so that we can
        # better exercise the circular dependency machinery.
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_gerrit.addFakeChange('org/project1', 'master', 'A')
        B = self.fake_gerrit.addFakeChange('org/project2', 'master', 'B')

        # A <-> B (via commit-depends)
        A.data["commitMessage"] = "{}\n\nDepends-On: {}\n".format(
            A.subject, B.data["url"]
        )
        B.data["commitMessage"] = "{}\n\nDepends-On: {}\n".format(
            B.subject, A.data["url"]
        )

        self.fake_gerrit.addEvent(A.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()
        self.fake_gerrit.addEvent(B.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        # We should never run jobs for more than one change
        # per-project at a time
        self.assertEqual(len(self.builds), 4)

        # This pair of changes should be superceded by the next
        C = self.fake_gerrit.addFakeChange('org/project1', 'master', 'C')
        D = self.fake_gerrit.addFakeChange('org/project2', 'master', 'D')

        # C <-> D (via commit-depends)
        C.data["commitMessage"] = "{}\n\nDepends-On: {}\n".format(
            C.subject, D.data["url"]
        )
        D.data["commitMessage"] = "{}\n\nDepends-On: {}\n".format(
            D.subject, C.data["url"]
        )

        self.fake_gerrit.addEvent(C.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()
        self.fake_gerrit.addEvent(D.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        # We should never run jobs for more than one change
        # per-project at a time
        self.assertEqual(len(self.builds), 4)

        # This change should supercede C
        E = self.fake_gerrit.addFakeChange('org/project1', 'master', 'E')
        self.fake_gerrit.addEvent(E.getPatchsetCreatedEvent(1))
        self.waitUntilSettled()

        # We should never run jobs for more than one change
        # per-project at a time
        self.assertEqual(len(self.builds), 4)

        self.executor_server.hold_jobs_in_build = True
        self.orderedRelease()
        self.assertHistory([
            dict(name='post-job', result='SUCCESS', changes="1,1"),
            dict(name='post1-job', result='SUCCESS', changes="1,1"),
            dict(name='post-job', result='SUCCESS', changes="2,1"),
            dict(name='post2-job', result='SUCCESS', changes="2,1"),
            dict(name='post-job', result='SUCCESS', changes="5,1"),
            dict(name='post1-job', result='SUCCESS', changes="5,1"),
            dict(name='post-job', result='SUCCESS', changes="4,1"),
            dict(name='post2-job', result='SUCCESS', changes="4,1"),
        ], ordered=False)

    @simple_layout('layouts/supercedent-circular-github.yaml', driver='github')
    def test_supercedent_github_circular_deps_merged(self):
        # We leave testing pre-merge changes to the gerrit test above.
        # In this test, we're testing post-merge change objects (not
        # refs) via github since there is a reasonable post-merge
        # pipeline configuration that triggers on those.
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_github.openFakePullRequest("org/project1", "master", "A")
        B = self.fake_github.openFakePullRequest("org/project2", "master", "B")

        # A <-> B (via PR-depends)
        A.body = "{}\n\nDepends-On: {}\n".format(
            A.subject, B.url,
        )
        B.body = "{}\n\nDepends-On: {}\n".format(
            B.subject, A.url
        )

        A.setMerged('merged')
        self.fake_github.emitEvent(A.getPullRequestClosedEvent())
        self.waitUntilSettled()
        B.setMerged('merged')
        self.fake_github.emitEvent(B.getPullRequestClosedEvent())
        self.waitUntilSettled()

        # We should never run jobs for more than one change
        # per-project at a time
        self.assertEqual(len(self.builds), 4)

        # This pair of changes should be superceded by the next
        C = self.fake_github.openFakePullRequest("org/project1", "master", "C")
        D = self.fake_github.openFakePullRequest("org/project2", "master", "D")

        # C <-> D (via PR-depends)
        C.body = "{}\n\nDepends-On: {}\n".format(
            C.subject, D.url,
        )
        D.body = "{}\n\nDepends-On: {}\n".format(
            D.subject, C.url
        )

        C.setMerged('merged')
        self.fake_github.emitEvent(C.getPullRequestClosedEvent())
        self.waitUntilSettled()
        D.setMerged('merged')
        self.fake_github.emitEvent(D.getPullRequestClosedEvent())
        self.waitUntilSettled()

        # We should never run jobs for more than one change
        # per-project at a time
        self.assertEqual(len(self.builds), 4)

        # This change should supercede C
        E = self.fake_github.openFakePullRequest("org/project1", "master", "E")
        E.setMerged('merged')
        self.fake_github.emitEvent(E.getPullRequestClosedEvent())
        self.waitUntilSettled()

        # We should never run jobs for more than one change
        # per-project at a time
        self.assertEqual(len(self.builds), 4)

        self.executor_server.hold_jobs_in_build = True
        self.orderedRelease()
        self.assertHistory([
            dict(name='post-job', result='SUCCESS',
                 changes=f"{A.number},{A.head_sha}"),
            dict(name='post1-job', result='SUCCESS',
                 changes=f"{A.number},{A.head_sha}"),
            dict(name='post-job', result='SUCCESS',
                 changes=f"{B.number},{B.head_sha}"),
            dict(name='post2-job', result='SUCCESS',
                 changes=f"{B.number},{B.head_sha}"),
            dict(name='post-job', result='SUCCESS',
                 changes=f"{E.number},{E.head_sha}"),
            dict(name='post1-job', result='SUCCESS',
                 changes=f"{E.number},{E.head_sha}"),
            dict(name='post-job', result='SUCCESS',
                 changes=f"{D.number},{D.head_sha}"),
            dict(name='post2-job', result='SUCCESS',
                 changes=f"{D.number},{D.head_sha}"),
        ], ordered=False)

    @simple_layout('layouts/supercedent-circular-github.yaml', driver='github')
    def test_supercedent_github_circular_deps_closed(self):
        # Run one change through the pipeline to force all the
        # zkobjects to be created so that the nologs check below
        # doesn't see the initial error message.
        C = self.fake_github.openFakePullRequest("org/project1", "master", "C")
        self.fake_github.emitEvent(C.getPullRequestClosedEvent())
        self.waitUntilSettled("create pipeline objects")
        # We leave testing pre-merge changes to the gerrit test above.
        # In this test, we're testing post-merge change objects (not
        # refs) via github since there is a reasonable post-merge
        # pipeline configuration that triggers on those.  This test
        # exercises the code path where the change is closed but not
        # merged (we should run no jobs, but we should also not fail
        # pipeline processing while dealing with circular deps).
        self.executor_server.hold_jobs_in_build = True
        A = self.fake_github.openFakePullRequest("org/project1", "master", "A")
        B = self.fake_github.openFakePullRequest("org/project2", "master", "B")

        # A <-> B (via PR-depends)
        A.body = "{}\n\nDepends-On: {}\n".format(
            A.subject, B.url,
        )
        B.body = "{}\n\nDepends-On: {}\n".format(
            B.subject, A.url
        )

        with self.assertNoLogs('zuul.Scheduler-0', level='ERROR'):
            self.fake_github.emitEvent(A.getPullRequestClosedEvent())
            self.waitUntilSettled()
            self.fake_github.emitEvent(B.getPullRequestClosedEvent())
            self.waitUntilSettled()
