// Copyright 2018 Red Hat, Inc
// Copyright 2025 Acme Gating, LLC
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

export const NODESET_REQUESTS_FETCH_REQUEST = 'NODESET_REQUESTS_FETCH_REQUEST'
export const NODESET_REQUESTS_FETCH_SUCCESS = 'NODESET_REQUESTS_FETCH_SUCCESS'
export const NODESET_REQUESTS_FETCH_FAIL = 'NODESET_REQUESTS_FETCH_FAIL'

export const requestNodesetRequests = () => ({
  type: NODESET_REQUESTS_FETCH_REQUEST
})

export const receiveNodesetRequests = (tenant, json) => ({
  type: NODESET_REQUESTS_FETCH_SUCCESS,
  requests: json,
  receivedAt: Date.now()
})

const failedNodesetRequests = error => ({
  type: NODESET_REQUESTS_FETCH_FAIL,
  error
})

const fetchNodesetRequests = (tenant) => dispatch => {
  dispatch(requestNodesetRequests())
  return API.fetchNodesetRequests(tenant.apiPrefix)
    .then(response => dispatch(receiveNodesetRequests(
      tenant.name, response.data)))
    .catch(error => dispatch(failedNodesetRequests(error)))
}

const shouldFetchNodesetRequests = (tenant, state) => {
  const requests = state.nodesetRequests
  if (!requests || requests.requests.length === 0) {
    return true
  }
  if (requests.isFetching) {
    return false
  }
  if (Date.now() - requests.receivedAt > 60000) {
    // Refetch after 1 minutes
    return true
  }
  return false
}

export const fetchNodesetRequestsIfNeeded = (tenant, force) => (
  dispatch, getState) => {
  if (force || shouldFetchNodesetRequests(tenant, getState())) {
    return dispatch(fetchNodesetRequests(tenant))
  }
}
