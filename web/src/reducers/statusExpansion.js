// Copyright 2024 Acme Gating, LLC
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.

import {
  STATUSEXPANSION_EXPAND_JOBS,
  STATUSEXPANSION_COLLAPSE_JOBS,
  STATUSEXPANSION_CLEANUP_JOBS,
  STATUSEXPANSION_CLEAR_JOBS,
  STATUSEXPANSION_EXPAND_QUEUE,
  STATUSEXPANSION_COLLAPSE_QUEUE,
  STATUSEXPANSION_CLEANUP_QUEUE,
  STATUSEXPANSION_CLEAR_QUEUE,
} from '../actions/statusExpansion'

export default (state = {
  expandedJobs: {},
  expandedQueue: {},
}, action) => {
  switch (action.type) {
    case STATUSEXPANSION_EXPAND_JOBS:
      return {
        ...state,
        expandedJobs: {...state.expandedJobs, [action.key]: true}
      }
    case STATUSEXPANSION_COLLAPSE_JOBS:
      return {
        ...state,
        expandedJobs: {...state.expandedJobs, [action.key]: false}
      }
    case STATUSEXPANSION_CLEANUP_JOBS:
      // eslint-disable-next-line
      const {[action.key]:unused, ...newJobs } = state.expandedJobs
      return {
        ...state,
        expandedJobs: newJobs,
      }
    case STATUSEXPANSION_EXPAND_QUEUE:
      return {
        ...state,
        expandedQueue: {...state.expandedQueue, [action.key]: true}
      }
    case STATUSEXPANSION_COLLAPSE_QUEUE:
      return {
        ...state,
        expandedQueue: {...state.expandedQueue, [action.key]: false}
      }
    case STATUSEXPANSION_CLEANUP_QUEUE:
      // eslint-disable-next-line
      const {[action.key]:unused2, ...newQueue } = state.expandedQueue
      return {
        ...state,
        expandedQueue: newQueue,
      }
    case STATUSEXPANSION_CLEAR_QUEUE:
      // also clears jobs
      return {
        ...state,
        expandedQueue: {},
        expandedJobs: {},
      }
    case STATUSEXPANSION_CLEAR_JOBS:
      return {
        ...state,
        expandedJobs: {},
      }
    default:
      return state
  }
}
