// Copyright 2020 Red Hat, Inc
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

export const AUTOHOLDS_FETCH_REQUEST = 'AUTOHOLDS_FETCH_REQUEST'
export const AUTOHOLDS_FETCH_SUCCESS = 'AUTOHOLDS_FETCH_SUCCESS'
export const AUTOHOLDS_FETCH_FAIL = 'AUTOHOLDS_FETCH_FAIL'

export const AUTOHOLD_FETCH_REQUEST = 'AUTOHOLD_FETCH_REQUEST'
export const AUTOHOLD_FETCH_SUCCESS = 'AUTOHOLD_FETCH_SUCCESS'
export const AUTOHOLD_FETCH_FAIL = 'AUTOHOLD_FETCH_FAIL'

export const requestAutoholds = () => ({
  type: AUTOHOLDS_FETCH_REQUEST
})

export const receiveAutoholds = (tenant, json) => ({
  type: AUTOHOLDS_FETCH_SUCCESS,
  autoholds: json,
  receivedAt: Date.now()
})

const failedAutoholds = error => ({
  type: AUTOHOLDS_FETCH_FAIL,
  error
})

export const fetchAutoholds = (tenant) => dispatch => {
  dispatch(requestAutoholds())
  return API.fetchAutoholds(tenant.apiPrefix)
    .then(response => dispatch(receiveAutoholds(tenant.name, response.data)))
    .catch(error => dispatch(failedAutoholds(error)))
}

const shouldFetchAutoholds = (tenant, state) => {
  const autoholds = state.autoholds
  if (!autoholds || autoholds.autoholds.length === 0) {
    return true
  }
  if (autoholds.isFetching) {
    return false
  }
  if (Date.now() - autoholds.receivedAt > 60000) {
    // Refetch after 1 minutes
    return true
  }
  return false
}

export const fetchAutoholdsIfNeeded = (tenant, force) => (
  dispatch, getState) => {
  if (force || shouldFetchAutoholds(tenant, getState())) {
    return dispatch(fetchAutoholds(tenant))
  }
}

export const requestAutohold = () => ({
  type: AUTOHOLD_FETCH_REQUEST
})

export const receiveAutohold = (tenant, json) => ({
  type: AUTOHOLD_FETCH_SUCCESS,
  autohold: json,
  receivedAt: Date.now()
})

const failedAutohold = error => ({
  type: AUTOHOLD_FETCH_FAIL,
  error
})

export const fetchAutohold = (tenant, requestId) => dispatch => {
  dispatch(requestAutohold())
  return API.fetchAutohold(tenant.apiPrefix, requestId)
    .then(response => dispatch(receiveAutohold(tenant.name, response.data)))
    .catch(error => dispatch(failedAutohold(error)))
}
