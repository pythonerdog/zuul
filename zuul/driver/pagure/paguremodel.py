# Copyright 2018 Red Hat, Inc.
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

from zuul.model import Change, TriggerEvent, EventFilter, RefFilter

EMPTY_GIT_REF = '0' * 40  # git sha of all zeros, used during creates/deletes


class PullRequest(Change):
    def __init__(self, project):
        super(PullRequest, self).__init__(project)
        self.pr = None
        self.updated_at = None
        self.title = None
        self.score = 0
        self.tags = []
        self.status = None

    def __repr__(self):
        r = ['<Change 0x%x' % id(self)]
        if self.project:
            r.append('project: %s' % self.project)
        if self.number:
            r.append('number: %s' % self.number)
        if self.patchset:
            r.append('patchset: %s' % self.patchset)
        if self.updated_at:
            r.append('updated: %s' % self.updated_at)
        if self.status:
            r.append('status: %s' % self.status)
        if self.score:
            r.append('score: %s' % self.score)
        if self.tags:
            r.append('tags: %s' % ', '.join(self.tags))
        if self.is_merged:
            r.append('state: merged')
        if self.open:
            r.append('state: open')
        return ' '.join(r) + '>'

    def serialize(self):
        d = super().serialize()
        d.update({
            "pr": self.pr,
            "updated_at": self.updated_at,
            "title": self.title,
            "score": self.score,
            "tags": self.tags,
            "status": self.status,
        })
        return d

    def deserialize(self, data):
        super().deserialize(data)
        self.pr = data.get("pr")
        self.updated_at = data.get("updated_at")
        self.title = data.get("title")
        self.score = data.get("score", 0)
        self.tags = data.get("tags", [])
        self.status = data.get("status")

    def isUpdateOf(self, other):
        if (self.project == other.project and
            hasattr(other, 'number') and self.number == other.number and
            hasattr(other, 'updated_at') and
            self.updated_at > other.updated_at):
            return True
        return False


class PagureTriggerEvent(TriggerEvent):
    def __init__(self):
        super(PagureTriggerEvent, self).__init__()
        self.trigger_name = 'pagure'
        self.title = None
        self.action = None
        self.initial_comment_changed = None
        self.status = None
        self.tags = []
        self.tag = None

    def toDict(self):
        d = super().toDict()
        d["trigger_name"] = self.trigger_name
        d["title"] = self.title
        d["action"] = self.action
        d["initial_comment_changed"] = self.initial_comment_changed
        d["status"] = self.status
        d["tags"] = list(self.tags)
        d["tag"] = self.tag
        return d

    def updateFromDict(self, d):
        super().updateFromDict(d)
        self.trigger_name = d.get("trigger_name", "pagure")
        self.title = d.get("title")
        self.action = d.get("action")
        self.initial_comment_changed = d.get("initial_comment_changed")
        self.status = d.get("status")
        self.tags = d.get("tags", [])
        self.tag = d.get("tag")

    def _repr(self):
        r = [super(PagureTriggerEvent, self)._repr()]
        if self.action:
            r.append("action:%s" % self.action)
        if self.status:
            r.append("status:%s" % self.status)
        r.append("project:%s" % self.canonical_project_name)
        if self.change_number:
            r.append("pr:%s" % self.change_number)
        if self.tags:
            r.append("tags:%s" % ', '.join(self.tags))
        return ' '.join(r)

    def isPatchsetCreated(self):
        if self.type == 'pg_pull_request':
            return self.action in ['opened', 'changed']
        return False

    def isMessageChanged(self):
        return bool(self.initial_comment_changed)


class PagureEventFilter(EventFilter):
    def __init__(self, connection_name, trigger, types=[], refs=[],
                 statuses=[], comments=[], actions=[], tags=[],
                 ignore_deletes=True):

        EventFilter.__init__(self, connection_name, trigger)

        self._types = [x.pattern for x in types]
        self._refs = [x.pattern for x in refs]
        self._comments = [x.pattern for x in comments]
        self.types = types
        self.refs = refs
        self.comments = comments
        self.actions = actions
        self.statuses = statuses
        self.tags = tags
        self.ignore_deletes = ignore_deletes

    def __repr__(self):
        ret = '<PagureEventFilter'
        ret += ' connection: %s' % self.connection_name

        if self._types:
            ret += ' types: %s' % ', '.join(self._types)
        if self._refs:
            ret += ' refs: %s' % ', '.join(self._refs)
        if self.ignore_deletes:
            ret += ' ignore_deletes: %s' % self.ignore_deletes
        if self._comments:
            ret += ' comments: %s' % ', '.join(self._comments)
        if self.actions:
            ret += ' actions: %s' % ', '.join(self.actions)
        if self.statuses:
            ret += ' statuses: %s' % ', '.join(self.statuses)
        if self.tags:
            ret += ' tags: %s' % ', '.join(self.tags)
        ret += '>'

        return ret

    def matches(self, event, change):
        if not super().matches(event, change):
            return False

        matches_type = False
        for etype in self.types:
            if etype.match(event.type):
                matches_type = True
        if self.types and not matches_type:
            return False

        matches_ref = False
        if event.ref is not None:
            for ref in self.refs:
                if ref.match(event.ref):
                    matches_ref = True
        if self.refs and not matches_ref:
            return False
        if self.ignore_deletes and event.newrev == EMPTY_GIT_REF:
            # If the updated ref has an empty git sha (all 0s),
            # then the ref is being deleted
            return False

        matches_comment_re = False
        for comment_re in self.comments:
            if (event.comment is not None and
                comment_re.search(event.comment)):
                matches_comment_re = True
        if self.comments and not matches_comment_re:
            return False

        matches_action = False
        for action in self.actions:
            if (event.action == action):
                matches_action = True
        if self.actions and not matches_action:
            return False

        matches_status = False
        for status in self.statuses:
            if event.status == status:
                matches_status = True
        if self.statuses and not matches_status:
            return False

        if self.tags:
            if not set(event.tags).intersection(set(self.tags)):
                return False

        return True


# The RefFilter should be understood as RequireFilter (it maps to
# pipeline requires definition)
class PagureRefFilter(RefFilter):
    def __init__(self, connection_name, score=None,
                 open=None, merged=None, status=None, tags=[]):
        RefFilter.__init__(self, connection_name)
        self.score = score
        self.open = open
        self.merged = merged
        self.status = status
        self.tags = tags

    def __repr__(self):
        ret = '<PagureRefFilter connection_name: %s ' % self.connection_name
        if self.score:
            ret += ' score: %s' % self.score
        if self.open is not None:
            ret += ' open: %s' % self.open
        if self.merged is not None:
            ret += ' merged: %s' % self.merged
        if self.status is not None:
            ret += ' status: %s' % self.status
        if self.tags:
            ret += ' tags: %s' % ', '.join(self.tags)
        ret += '>'
        return ret

    def matches(self, change):
        if self.score is not None:
            if change.score < self.score:
                return False

        if self.open is not None:
            if change.open != self.open:
                return False

        if self.merged is not None:
            if change.is_merged != self.merged:
                return False

        if self.status is not None:
            if change.status != self.status:
                return False

        if self.tags:
            if not set(change.tags).intersection(set(self.tags)):
                return False

        return True
