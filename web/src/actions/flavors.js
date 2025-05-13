// Copyright 2018 Red Hat, Inc
// Copyright 2022, 2024 Acme Gating, LLC
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

export const FLAVORS_FETCH_REQUEST = 'FLAVORS_FETCH_REQUEST'
export const FLAVORS_FETCH_SUCCESS = 'FLAVORS_FETCH_SUCCESS'
export const FLAVORS_FETCH_FAIL = 'FLAVORS_FETCH_FAIL'

export const requestFlavors = () => ({
  type: FLAVORS_FETCH_REQUEST
})

export const receiveFlavors = (tenant, json) => ({
  type: FLAVORS_FETCH_SUCCESS,
  tenant: tenant,
  flavors: json,
  receivedAt: Date.now()
})

const failedFlavors = error => ({
  type: FLAVORS_FETCH_FAIL,
  error
})

export const fetchFlavors = (tenant) => dispatch => {
  dispatch(requestFlavors())
  return API.fetchFlavors(tenant.apiPrefix)
    .then(response => dispatch(receiveFlavors(tenant.name, response.data)))
    .catch(error => dispatch(failedFlavors(error)))
}

const shouldFetchFlavors = (tenant, state) => {
  const flavors = state.flavors.flavors[tenant.name]
  if (!flavors) {
    return true
  }
  if (flavors.isFetching) {
    return false
  }
  return false
}

export const fetchFlavorsIfNeeded = (tenant) => (dispatch, getState) => {
  if (shouldFetchFlavors(tenant, getState())) {
    return dispatch(fetchFlavors(tenant))
  }
  return Promise.resolve()
}
