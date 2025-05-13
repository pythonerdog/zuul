// Copyright 2018 Red Hat, Inc
// Copyright 2022 Acme Gating, LLC
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

import * as API from '../api'

export const FREEZE_JOB_FETCH_REQUEST = 'FREEZE_JOB_FETCH_REQUEST'
export const FREEZE_JOB_FETCH_SUCCESS = 'FREEZE_JOB_FETCH_SUCCESS'
export const FREEZE_JOB_FETCH_FAIL = 'FREEZE_JOB_FETCH_FAIL'

export const requestFreezeJob = () => ({
  type: FREEZE_JOB_FETCH_REQUEST
})

export function makeFreezeJobKey(pipeline, project, branch, job) {
  return JSON.stringify({
    pipeline, project, branch, job
  })
}

export const receiveFreezeJob = (tenant, freezeJobKey, freezeJob) => {
  return {
    type: FREEZE_JOB_FETCH_SUCCESS,
    tenant: tenant,
    freezeJobKey: freezeJobKey,
    freezeJob: freezeJob,
    receivedAt: Date.now(),
  }
}

const failedFreezeJob = error => ({
  type: FREEZE_JOB_FETCH_FAIL,
  error
})

const fetchFreezeJob = (tenant, pipeline, project, branch, job) => dispatch => {
  dispatch(requestFreezeJob())
  const freezeJobKey = makeFreezeJobKey(pipeline, project, branch, job)
  return API.fetchFreezeJob(tenant.apiPrefix,
                            pipeline,
                            project,
                            branch,
                            job)
    .then(response => dispatch(receiveFreezeJob(
      tenant.name, freezeJobKey, response.data)))
    .catch(error => dispatch(failedFreezeJob(error)))
}

const shouldFetchFreezeJob = (tenant, pipeline, project, branch, job, state) => {
  const freezeJobKey = makeFreezeJobKey(pipeline, project, branch, job)
  const tenantFreezeJobs = state.freezejob.freezeJobs[tenant.name]
  if (tenantFreezeJobs) {
    const freezeJob = tenantFreezeJobs[freezeJobKey]
    if (!freezeJob) {
      return true
    }
    if (freezeJob.isFetching) {
      return false
    }
    return false
  }
  return true
}

export const fetchFreezeJobIfNeeded = (tenant, pipeline, project, branch, job,
                                      force) => (
  dispatch, getState) => {
    if (force || shouldFetchFreezeJob(tenant, pipeline, project, branch, job,
                                     getState())) {
      return dispatch(fetchFreezeJob(tenant, pipeline, project, branch, job))
  }
  return Promise.resolve()
}
