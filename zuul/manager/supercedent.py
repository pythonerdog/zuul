# Copyright 2021, 2023-2024 Acme Gating, LLC
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

from zuul import model
from zuul.lib.logutil import get_annotated_logger
from zuul.manager import PipelineManager, DynamicChangeQueueContextManager


class SupercedentPipelineManager(PipelineManager):
    """PipelineManager with one queue per project and a window of 1"""

    changes_merge = False
    type = 'supercedent'

    def getChangeQueue(self, change, event, existing=None):
        log = get_annotated_logger(self.log, event)

        # creates a new change queue for every project-ref
        # combination.
        if existing:
            return DynamicChangeQueueContextManager(existing)

        # Don't use Pipeline.getQueue to find an existing queue
        # because we're matching project and (branch or ref).
        for queue in self.state.queues:
            if (queue.queue[-1].changes[0].project == change.project and
                ((hasattr(change, 'branch') and
                  hasattr(queue.queue[-1].changes[0], 'branch') and
                  queue.queue[-1].changes[0].branch == change.branch) or
                queue.queue[-1].changes[0].ref == change.ref)):
                log.debug("Found existing queue %s", queue)
                return DynamicChangeQueueContextManager(queue)
        change_queue = model.ChangeQueue.new(
            self.current_context,
            manager=self,
            window=1,
            window_floor=1,
            window_ceiling=1,
            window_increase_type='none',
            window_decrease_type='none',
            dynamic=True)
        change_queue.addProject(change.project, None)
        self.state.addQueue(change_queue)
        log.debug("Dynamically created queue %s", change_queue)
        return DynamicChangeQueueContextManager(
            change_queue, allow_delete=True)

    def _pruneQueues(self):
        # Leave the first item in the queue, as it's running, and the
        # last item, as it's the most recent, but remove any items in
        # between.  This is what causes the last item to "supercede"
        # any previously enqueued items (which we know aren't running
        # jobs because the window size is 1).
        for queue in self.state.queues[:]:
            remove = queue.queue[1:-1]
            for item in remove:
                self.log.debug("Item %s is superceded by %s, removing" %
                               (item, queue.queue[-1]))
                self.removeItem(item)

    def cycleForChange(self, *args, **kw):
        # Supercedent pipelines ignore circular dependencies and
        # individually enqueue each change that matches the trigger.
        # This is because they ignore shared queues and instead create
        # a virtual queue for each project-ref.
        return []

    def addChange(self, *args, **kw):
        ret = super(SupercedentPipelineManager, self).addChange(
            *args, **kw)
        if ret:
            self._pruneQueues()
        return ret

    def dequeueItem(self, item, quiet=False):
        super(SupercedentPipelineManager, self).dequeueItem(item, quiet)
        # A supercedent pipeline manager dynamically removes empty
        # queues
        if not item.queue.queue:
            self.state.removeQueue(item.queue)
