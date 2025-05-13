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

export const PROVIDERS_FETCH_REQUEST = 'PROVIDERS_FETCH_REQUEST'
export const PROVIDERS_FETCH_SUCCESS = 'PROVIDERS_FETCH_SUCCESS'
export const PROVIDERS_FETCH_FAIL = 'PROVIDERS_FETCH_FAIL'

export const requestProviders = () => ({
  type: PROVIDERS_FETCH_REQUEST
})

export const receiveProviders = (tenant, json) => ({
  type: PROVIDERS_FETCH_SUCCESS,
  tenant: tenant,
  providers: json,
  receivedAt: Date.now()
})

const failedProviders = error => ({
  type: PROVIDERS_FETCH_FAIL,
  error
})

export const fetchProviders = (tenant) => dispatch => {
  dispatch(requestProviders())
  return API.fetchProviders(tenant.apiPrefix)
    .then(response => dispatch(receiveProviders(tenant.name, response.data)))
    .catch(error => dispatch(failedProviders(error)))
}

const shouldFetchProviders = (tenant, state) => {
  const providers = state.providers.providers[tenant.name]
  if (!providers) {
    return true
  }
  if (providers.isFetching) {
    return false
  }
  return false
}

export const fetchProvidersIfNeeded = (tenant) => (dispatch, getState) => {
  if (shouldFetchProviders(tenant, getState())) {
    return dispatch(fetchProviders(tenant))
  }
  return Promise.resolve()
}
