# Copyright 2012 Hewlett-Packard Development Company, L.P.
# Copyright 2016 Red Hat, Inc.
# Copyright 2021-2024 Acme Gating, LLC
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
import logging
import os
import re
import time
import uuid

import zuul.driver.pagure.pagureconnection as pagureconnection

import git
import requests


class PagureChangeReference(git.Reference):
    _common_path_default = "refs/pull"
    _points_to_commits_only = True


class FakePagurePullRequest(object):
    log = logging.getLogger("zuul.test.FakePagurePullRequest")

    def __init__(self, pagure, number, project, branch,
                 subject, upstream_root, files={}, number_of_commits=1,
                 initial_comment=None):
        self.source_hostname = pagure.canonical_hostname
        self.pagure_server = pagure.server
        self.number = number
        self.project = project
        self.branch = branch
        self.subject = subject
        self.upstream_root = upstream_root
        self.number_of_commits = 0
        self.status = 'Open'
        self.initial_comment = initial_comment
        self.uuid = uuid.uuid4().hex
        self.comments = []
        self.flags = []
        self.files = {}
        self.tags = []
        self.cached_merge_status = ''
        self.threshold_reached = False
        self.commit_stop = None
        self.commit_start = None
        self.threshold_reached = False
        self.upstream_root = upstream_root
        self.cached_merge_status = 'MERGE'
        self.url = "https://%s/%s/pull-request/%s" % (
            self.pagure_server, self.project, self.number)
        self.is_merged = False
        self.pr_ref = self._createPRRef()
        self._addCommitInPR(files=files)
        self._updateTimeStamp()

    def _getPullRequestEvent(self, action, pull_data_field='pullrequest'):
        name = 'pg_pull_request'
        data = {
            'msg': {
                pull_data_field: {
                    'branch': self.branch,
                    'comments': self.comments,
                    'commit_start': self.commit_start,
                    'commit_stop': self.commit_stop,
                    'date_created': '0',
                    'tags': self.tags,
                    'initial_comment': self.initial_comment,
                    'id': self.number,
                    'project': {
                        'fullname': self.project,
                    },
                    'status': self.status,
                    'subject': self.subject,
                    'uid': self.uuid,
                }
            },
            'msg_id': str(uuid.uuid4()),
            'timestamp': 1427459070,
            'topic': action
        }
        if action == 'pull-request.flag.added':
            data['msg']['flag'] = self.flags[0]
        if action == 'pull-request.tag.added':
            data['msg']['tags'] = self.tags
        return (name, data)

    def getPullRequestOpenedEvent(self):
        return self._getPullRequestEvent('pull-request.new')

    def getPullRequestClosedEvent(self, merged=True):
        if merged:
            self.is_merged = True
            self.status = 'Merged'
        else:
            self.is_merged = False
            self.status = 'Closed'
        return self._getPullRequestEvent('pull-request.closed')

    def getPullRequestUpdatedEvent(self):
        self._addCommitInPR()
        self.addComment(
            "**1 new commit added**\n\n * ``Bump``\n",
            True)
        return self._getPullRequestEvent('pull-request.comment.added')

    def getPullRequestCommentedEvent(self, message):
        self.addComment(message)
        return self._getPullRequestEvent('pull-request.comment.added')

    def getPullRequestInitialCommentEvent(self, message):
        self.initial_comment = message
        self._updateTimeStamp()
        return self._getPullRequestEvent('pull-request.initial_comment.edited')

    def getPullRequestTagAddedEvent(self, tags, reset=True):
        if reset:
            self.tags = []
        _tags = set(self.tags)
        _tags.update(set(tags))
        self.tags = list(_tags)
        self.addComment(
            "**Metadata Update from @pingou**:\n- " +
            "Pull-request tagged with: %s" % ', '.join(tags),
            True)
        self._updateTimeStamp()
        return self._getPullRequestEvent(
            'pull-request.tag.added', pull_data_field='pull_request')

    def getPullRequestStatusSetEvent(self, status, username="zuul"):
        self.addFlag(
            status, "https://url", "Build %s" % status, username)
        return self._getPullRequestEvent('pull-request.flag.added')

    def insertFlag(self, flag):
        to_pop = None
        for i, _flag in enumerate(self.flags):
            if _flag['uid'] == flag['uid']:
                to_pop = i
        if to_pop is not None:
            self.flags.pop(to_pop)
        self.flags.insert(0, flag)

    def addFlag(self, status, url, comment, username="zuul"):
        flag_uid = "%s-%s-%s" % (username, self.number, self.project)
        flag = {
            "username": "Zuul CI",
            "user": {
                "name": username
            },
            "uid": flag_uid[:32],
            "comment": comment,
            "status": status,
            "url": url
        }
        self.insertFlag(flag)
        self._updateTimeStamp()

    def editInitialComment(self, initial_comment):
        self.initial_comment = initial_comment
        self._updateTimeStamp()

    def addComment(self, message, notification=False, fullname=None):
        self.comments.append({
            'comment': message,
            'notification': notification,
            'date_created': str(int(time.time())),
            'user': {
                'fullname': fullname or 'Pingou'
            }}
        )
        self._updateTimeStamp()

    def getPRReference(self):
        return '%s/head' % self.number

    def _getRepo(self):
        repo_path = os.path.join(self.upstream_root, self.project)
        return git.Repo(repo_path)

    def _createPRRef(self):
        repo = self._getRepo()
        return PagureChangeReference.create(
            repo, self.getPRReference(), 'refs/tags/init')

    def addCommit(self, files={}, delete_files=None):
        """Adds a commit on top of the actual PR head."""
        self._addCommitInPR(files=files, delete_files=delete_files)
        self._updateTimeStamp()

    def forcePush(self, files={}):
        """Clears actual commits and add a commit on top of the base."""
        self._addCommitInPR(files=files, reset=True)
        self._updateTimeStamp()

    def _addCommitInPR(self, files={}, delete_files=None, reset=False):
        repo = self._getRepo()
        ref = repo.references[self.getPRReference()]
        if reset:
            self.number_of_commits = 0
            ref.set_object('refs/tags/init')
        self.number_of_commits += 1
        repo.head.reference = ref
        repo.git.clean('-x', '-f', '-d')

        if files:
            self.files = files
        elif not delete_files:
            fn = '%s-%s' % (self.branch.replace('/', '_'), self.number)
            self.files = {fn: "test %s %s\n" % (self.branch, self.number)}
        msg = self.subject + '-' + str(self.number_of_commits)
        for fn, content in self.files.items():
            fn = os.path.join(repo.working_dir, fn)
            with open(fn, 'w') as f:
                f.write(content)
            repo.index.add([fn])

        if delete_files:
            for fn in delete_files:
                if fn in self.files:
                    del self.files[fn]
                fn = os.path.join(repo.working_dir, fn)
                repo.index.remove([fn])

        self.commit_stop = repo.index.commit(msg).hexsha
        if not self.commit_start:
            self.commit_start = self.commit_stop

        repo.create_head(self.getPRReference(), self.commit_stop, force=True)
        self.pr_ref.set_commit(self.commit_stop)
        repo.head.reference = 'master'
        repo.git.clean('-x', '-f', '-d')
        repo.heads['master'].checkout()

    def _updateTimeStamp(self):
        self.last_updated = str(int(time.time()))


class FakePagureAPIClient(pagureconnection.PagureAPIClient):
    log = logging.getLogger("zuul.test.FakePagureAPIClient")

    def __init__(self, baseurl, api_token, project,
                 pull_requests_db={}):
        super(FakePagureAPIClient, self).__init__(
            baseurl, api_token, project)
        self.session = None
        self.pull_requests = pull_requests_db
        self.return_post_error = None

    def gen_error(self, verb, custom_only=False):
        if verb == 'POST' and self.return_post_error:
            return {
                'error': self.return_post_error['error'],
                'error_code': self.return_post_error['error_code']
            }, 401, "", 'POST'
            self.return_post_error = None
        if not custom_only:
            return {
                'error': 'some error',
                'error_code': 'some error code'
            }, 503, "", verb

    def _get_pr(self, match):
        project, number = match.groups()
        pr = self.pull_requests.get(project, {}).get(number)
        if not pr:
            return self.gen_error("GET")
        return pr

    def get(self, url):
        self.log.debug("Getting resource %s ..." % url)

        match = re.match(r'.+/api/0/(.+)/pull-request/(\d+)$', url)
        if match:
            pr = self._get_pr(match)
            return {
                'branch': pr.branch,
                'subject': pr.subject,
                'status': pr.status,
                'initial_comment': pr.initial_comment,
                'last_updated': pr.last_updated,
                'comments': pr.comments,
                'commit_stop': pr.commit_stop,
                'threshold_reached': pr.threshold_reached,
                'cached_merge_status': pr.cached_merge_status,
                'tags': pr.tags,
            }, 200, "", "GET"

        match = re.match(r'.+/api/0/(.+)/pull-request/(\d+)/flag$', url)
        if match:
            pr = self._get_pr(match)
            return {'flags': pr.flags}, 200, "", "GET"

        match = re.match('.+/api/0/(.+)/git/branches$', url)
        if match:
            # project = match.groups()[0]
            return {'branches': ['master']}, 200, "", "GET"

        match = re.match(r'.+/api/0/(.+)/pull-request/(\d+)/diffstats$', url)
        if match:
            pr = self._get_pr(match)
            return pr.files, 200, "", "GET"

    def post(self, url, params=None):

        self.log.info(
            "Posting on resource %s, params (%s) ..." % (url, params))

        # Will only match if return_post_error is set
        err = self.gen_error("POST", custom_only=True)
        if err:
            return err

        match = re.match(r'.+/api/0/(.+)/pull-request/(\d+)/merge$', url)
        if match:
            pr = self._get_pr(match)
            pr.status = 'Merged'
            pr.is_merged = True
            return {}, 200, "", "POST"

        match = re.match(r'.+/api/0/-/whoami$', url)
        if match:
            return {"username": "zuul"}, 200, "", "POST"

        if not params:
            return self.gen_error("POST")

        match = re.match(r'.+/api/0/(.+)/pull-request/(\d+)/flag$', url)
        if match:
            pr = self._get_pr(match)
            params['user'] = {"name": "zuul"}
            pr.insertFlag(params)

        match = re.match(r'.+/api/0/(.+)/pull-request/(\d+)/comment$', url)
        if match:
            pr = self._get_pr(match)
            pr.addComment(params['comment'])

        return {}, 200, "", "POST"


class FakePagureConnection(pagureconnection.PagureConnection):
    log = logging.getLogger("zuul.test.FakePagureConnection")

    def __init__(self, driver, connection_name, connection_config,
                 changes_db=None, upstream_root=None):
        super(FakePagureConnection, self).__init__(driver, connection_name,
                                                   connection_config)
        self.connection_name = connection_name
        self.pr_number = 0
        self.pull_requests = changes_db
        self.statuses = {}
        self.upstream_root = upstream_root
        self.reports = []
        self.cloneurl = self.upstream_root

    def get_project_api_client(self, project):
        client = FakePagureAPIClient(
            self.baseurl, None, project,
            pull_requests_db=self.pull_requests)
        if not self.username:
            self.set_my_username(client)
        return client

    def get_project_webhook_token(self, project, force_refresh=False):
        return 'fake_webhook_token-%s' % project

    def emitEvent(self, event, use_zuulweb=False, project=None,
                  wrong_token=False):
        name, payload = event
        if use_zuulweb:
            if not wrong_token:
                secret = 'fake_webhook_token-%s' % project
            else:
                secret = ''
            payload = json.dumps(payload).encode('utf-8')
            signature, _ = pagureconnection._sign_request(payload, secret)
            headers = {'x-pagure-signature': signature,
                       'x-pagure-project': project}
            return requests.post(
                'http://127.0.0.1:%s/api/connection/%s/payload'
                % (self.zuul_web_port, self.connection_name),
                data=payload, headers=headers)
        else:
            data = {'payload': payload}
            self.event_queue.put(data)
            return data

    def openFakePullRequest(self, project, branch, subject, files=[],
                            initial_comment=None):
        self.pr_number += 1
        pull_request = FakePagurePullRequest(
            self, self.pr_number, project, branch, subject, self.upstream_root,
            files=files, initial_comment=initial_comment)
        self.pull_requests.setdefault(
            project, {})[str(self.pr_number)] = pull_request
        return pull_request

    def getGitReceiveEvent(self, project):
        name = 'pg_push'
        repo_path = os.path.join(self.upstream_root, project)
        repo = git.Repo(repo_path)
        headsha = repo.head.commit.hexsha
        data = {
            'msg': {
                'project_fullname': project,
                'branch': 'master',
                'end_commit': headsha,
                'old_commit': '1' * 40,
            },
            'msg_id': str(uuid.uuid4()),
            'timestamp': 1427459070,
            'topic': 'git.receive',
        }
        return (name, data)

    def getGitTagCreatedEvent(self, project, tag, rev):
        name = 'pg_push'
        data = {
            'msg': {
                'project_fullname': project,
                'tag': tag,
                'rev': rev
            },
            'msg_id': str(uuid.uuid4()),
            'timestamp': 1427459070,
            'topic': 'git.tag.creation',
        }
        return (name, data)

    def getGitBranchEvent(self, project, branch, type, rev):
        name = 'pg_push'
        data = {
            'msg': {
                'project_fullname': project,
                'branch': branch,
                'rev': rev,
            },
            'msg_id': str(uuid.uuid4()),
            'timestamp': 1427459070,
            'topic': 'git.branch.%s' % type,
        }
        return (name, data)

    def setZuulWebPort(self, port):
        self.zuul_web_port = port
