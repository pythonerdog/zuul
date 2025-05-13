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

export const JOB_GRAPH_FETCH_REQUEST = 'JOB_GRAPH_FETCH_REQUEST'
export const JOB_GRAPH_FETCH_SUCCESS = 'JOB_GRAPH_FETCH_SUCCESS'
export const JOB_GRAPH_FETCH_FAIL = 'JOB_GRAPH_FETCH_FAIL'

export const requestJobGraph = () => ({
  type: JOB_GRAPH_FETCH_REQUEST
})

export function makeJobGraphKey(project, pipeline, branch) {
  return JSON.stringify({
    project: project, pipeline: pipeline, branch: branch
  })
}

export const receiveJobGraph = (tenant, jobGraphKey, jobGraph) => {
  return {
    type: JOB_GRAPH_FETCH_SUCCESS,
    tenant: tenant,
    jobGraphKey: jobGraphKey,
    jobGraph: jobGraph,
    receivedAt: Date.now(),
  }
}

const failedJobGraph = error => ({
  type: JOB_GRAPH_FETCH_FAIL,
  error
})

const fetchJobGraph = (tenant, project, pipeline, branch) => dispatch => {
  dispatch(requestJobGraph())
  const jobGraphKey = makeJobGraphKey(project, pipeline, branch)
  return API.fetchJobGraph(tenant.apiPrefix,
                           project,
                           pipeline,
                           branch)
    .then(response => dispatch(receiveJobGraph(
      tenant.name, jobGraphKey, response.data)))
    .catch(error => dispatch(failedJobGraph(error)))
}

const shouldFetchJobGraph = (tenant, project, pipeline, branch, state) => {
  const jobGraphKey = makeJobGraphKey(project, pipeline, branch)
  const tenantJobGraphs = state.jobgraph.jobGraphs[tenant.name]
  if (tenantJobGraphs) {
    const jobGraph = tenantJobGraphs[jobGraphKey]
    if (!jobGraph) {
      return true
    }
    if (jobGraph.isFetching) {
      return false
    }
    return false
  }
  return true
}

export const fetchJobGraphIfNeeded = (tenant, project, pipeline, branch,
                                      force) => (
  dispatch, getState) => {
    if (force || shouldFetchJobGraph(tenant, project, pipeline, branch,
                                     getState())) {
      return dispatch(fetchJobGraph(tenant, project, pipeline, branch))
  }
  return Promise.resolve()
}
