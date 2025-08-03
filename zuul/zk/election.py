# Copyright 2021 Acme Gating, LLC
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

import logging
import threading

from zuul.zk.components import COMPONENT_REGISTRY
from zuul.zk.locks import SessionAwareLock, locked

import mmh3
from kazoo.protocol.states import KazooState
from kazoo.recipe.election import Election
from kazoo.exceptions import CancelledError


class SessionAwareElection(Election):
    def __init__(self, client, path, identifier=None):
        self._zuul_session_expired = False
        super().__init__(client, path, identifier)

    def run(self, func, *args, **kwargs):
        self._zuul_session_expired = False
        self.lock.client.add_listener(self._zuul_session_watcher)
        try:
            return super().run(func, *args, **kwargs)
        finally:
            self.lock.client.remove_listener(self._zuul_session_watcher)

    def _zuul_session_watcher(self, state):
        if state == KazooState.LOST:
            self._zuul_session_expired = True

    def is_still_valid(self):
        return not self._zuul_session_expired


def _default_filter(x):
    return x.state == x.RUNNING


class RendezvousElection:
    def __init__(self, client, path, component_type, this_component,
                 component_filter=None):
        self.log = logging.getLogger("zuul.RendezvousElection")
        self.client = client
        self.component_type = component_type
        self.component_filter = component_filter or _default_filter
        self.this_component = this_component
        self.client = client
        self.path = path
        self.lock = SessionAwareLock(self.client, self.path)
        # Whether we are the current winner of the rendezvous hash
        self.is_winner = None
        self.component_change_event = threading.Event()
        COMPONENT_REGISTRY.registry.registerCallback(self._onComponentChange)

    # Similar to the Election API
    def run(self, func, *args, **kw):
        # Allow the cancel method to stop this loop
        # Handle a restart
        self.running = True
        if self.is_winner is None:
            self._checkWinner()
        while self.running:
            if not self.is_winner:
                self.log.debug("Did not win election for %s", self.path)
                self.component_change_event.wait()
                self.component_change_event.clear()
                continue
            try:
                self.log.debug("Acquiring lock for %s", self.path)
                with locked(self.lock):
                    self.log.info("Won election for %s", self.path)
                    func(*args, **kw)
            except CancelledError:
                pass
            finally:
                self.log.info("Finished term for %s", self.path)

    # Similar to the Election API
    def cancel(self):
        self.running = False
        self.is_winner = None
        self.lock.cancel()
        self.component_change_event.set()

    # Similar to the Lock API
    def is_still_valid(self):
        if self.is_winner:
            return self.lock.is_still_valid()
        return False

    def _getScores(self):
        return {
            mmh3.hash(f"{c.hostname}-{self.path}", signed=False): c
            for c in COMPONENT_REGISTRY.registry.all(self.component_type)
            if self.component_filter(c)
        }

    def _getWinner(self):
        scores = self._getScores()
        winner = None
        if scores:
            sorted_scores = sorted(scores.keys())
            best_score = sorted_scores[0]
            winner = scores[best_score]
        return winner

    def _checkWinner(self):
        winner = self._getWinner()
        self.log.debug("Election winner for %s is %s", self.path, winner)
        self.is_winner = (
            winner and
            winner.hostname == self.this_component.hostname
        )

    def _onComponentChange(self):
        self._checkWinner()
        self.component_change_event.set()
