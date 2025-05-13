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

export const STATUSEXPANSION_EXPAND_JOBS = 'STATUSEXPANSION_EXPAND_JOBS'
export const STATUSEXPANSION_COLLAPSE_JOBS = 'STATUSEXPANSION_COLLAPSE_JOBS'
export const STATUSEXPANSION_CLEANUP_JOBS = 'STATUSEXPANSION_CLEANUP_JOBS'
export const STATUSEXPANSION_CLEAR_JOBS = 'STATUSEXPANSION_CLEAR_JOBS'

export const STATUSEXPANSION_EXPAND_QUEUE = 'STATUSEXPANSION_EXPAND_QUEUE'
export const STATUSEXPANSION_COLLAPSE_QUEUE = 'STATUSEXPANSION_COLLAPSE_QUEUE'
export const STATUSEXPANSION_CLEANUP_QUEUE = 'STATUSEXPANSION_CLEANUP_QUEUE'
export const STATUSEXPANSION_CLEAR_QUEUE = 'STATUSEXPANSION_CLEAR_QUEUE'

const expandJobsAction = (key) => ({
  type: STATUSEXPANSION_EXPAND_JOBS,
  key: key,
})

const collapseJobsAction = (key) => ({
  type: STATUSEXPANSION_COLLAPSE_JOBS,
  key: key,
})

const cleanupJobsAction = (key) => ({
  type: STATUSEXPANSION_CLEANUP_JOBS,
  key: key,
})

const clearJobsAction = () => ({
  type: STATUSEXPANSION_CLEAR_JOBS,
})

const expandQueueAction = (key) => ({
  type: STATUSEXPANSION_EXPAND_QUEUE,
  key: key,
})

const collapseQueueAction = (key) => ({
  type: STATUSEXPANSION_COLLAPSE_QUEUE,
  key: key,
})

const cleanupQueueAction = (key) => ({
  type: STATUSEXPANSION_CLEANUP_QUEUE,
  key: key,
})

const clearQueueAction = () => ({
  type: STATUSEXPANSION_CLEAR_QUEUE,
})

export const expandJobs = (key) => (dispatch) => {
  dispatch(expandJobsAction(key))
}

export const collapseJobs = (key) => (dispatch) => {
  dispatch(collapseJobsAction(key))
}

export const cleanupJobs = (key) => (dispatch) => {
  dispatch(cleanupJobsAction(key))
}

export const clearJobs = () => (dispatch) => {
  dispatch(clearJobsAction())
}

export const expandQueue = (key) => (dispatch) => {
  dispatch(expandQueueAction(key))
}

export const collapseQueue = (key) => (dispatch) => {
  dispatch(collapseQueueAction(key))
}

export const cleanupQueue = (key) => (dispatch) => {
  dispatch(cleanupQueueAction(key))
}

export const clearQueue = () => (dispatch) => {
  dispatch(clearQueueAction())
}
