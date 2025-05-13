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

export const SEMAPHORES_FETCH_REQUEST = 'SEMAPHORES_FETCH_REQUEST'
export const SEMAPHORES_FETCH_SUCCESS = 'SEMAPHORES_FETCH_SUCCESS'
export const SEMAPHORES_FETCH_FAIL = 'SEMAPHORES_FETCH_FAIL'

export const requestSemaphores = () => ({
  type: SEMAPHORES_FETCH_REQUEST
})

export const receiveSemaphores = (tenant, json) => ({
  type: SEMAPHORES_FETCH_SUCCESS,
  tenant: tenant,
  semaphores: json,
  receivedAt: Date.now()
})

const failedSemaphores = error => ({
  type: SEMAPHORES_FETCH_FAIL,
  error
})

const fetchSemaphores = (tenant) => dispatch => {
  dispatch(requestSemaphores())
  return API.fetchSemaphores(tenant.apiPrefix)
    .then(response => dispatch(receiveSemaphores(tenant.name, response.data)))
    .catch(error => dispatch(failedSemaphores(error)))
}

const shouldFetchSemaphores = (tenant, state) => {
  const semaphores = state.semaphores.semaphores[tenant.name]
  if (!semaphores || semaphores.length === 0) {
    return true
  }
  if (semaphores.isFetching) {
    return false
  }
  return false
}

export const fetchSemaphoresIfNeeded = (tenant, force) => (dispatch, getState) => {
  if (force || shouldFetchSemaphores(tenant, getState())) {
    return dispatch(fetchSemaphores(tenant))
  }
  return Promise.resolve()
}
