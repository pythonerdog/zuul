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

export const PIPELINES_FETCH_REQUEST = 'PIPELINES_FETCH_REQUEST'
export const PIPELINES_FETCH_SUCCESS = 'PIPELINES_FETCH_SUCCESS'
export const PIPELINES_FETCH_FAIL = 'PIPELINES_FETCH_FAIL'

export const requestPipelines = () => ({
  type: PIPELINES_FETCH_REQUEST
})

export const receivePipelines = (tenant, json) => ({
  type: PIPELINES_FETCH_SUCCESS,
  tenant: tenant,
  pipelines: json,
  receivedAt: Date.now()
})

const failedPipelines = error => ({
  type: PIPELINES_FETCH_FAIL,
  error
})

const fetchPipelines = (tenant) => dispatch => {
  dispatch(requestPipelines())
  return API.fetchPipelines(tenant.apiPrefix)
    .then(response => dispatch(receivePipelines(tenant.name, response.data)))
    .catch(error => dispatch(failedPipelines(error)))
}

const shouldFetchPipelines = (tenant, state) => {
  const pipelines = state.pipelines.pipelines[tenant.name]
  if (!pipelines || pipelines.length === 0) {
    return true
  }
  if (pipelines.isFetching) {
    return false
  }
  return false
}

export const fetchPipelinesIfNeeded = (tenant, force) => (
  dispatch, getState) => {
  if (force || shouldFetchPipelines(tenant, getState())) {
    return dispatch(fetchPipelines(tenant))
  }
  return Promise.resolve()
}
