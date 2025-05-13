// Copyright 2018 Red Hat, Inc
// Copyright 2023 Acme Gating, LLC
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

import { fetchTenantStatus } from '../api'

export const TENANT_STATUS_FETCH_REQUEST = 'TENANT_STATUS_FETCH_REQUEST'
export const TENANT_STATUS_FETCH_SUCCESS = 'TENANT_STATUS_FETCH_SUCCESS'
export const TENANT_STATUS_FETCH_FAIL = 'TENANT_STATUS_FETCH_FAIL'
export const TENANT_STATUS_CLEAR = 'TENANT_STATUS_CLEAR'

export const requestTenantStatus = (tenant) => ({
  type: TENANT_STATUS_FETCH_REQUEST,
  tenant: tenant,
})

export const receiveTenantStatus = (tenant, json) => ({
  type: TENANT_STATUS_FETCH_SUCCESS,
  tenant: tenant,
  tenant_status: json,
  receivedAt: Date.now()
})

const failedTenantStatus = (tenant, error) => ({
  type: TENANT_STATUS_FETCH_FAIL,
  tenant: tenant,
  error
})

export function fetchTenantStatusAction (tenant) {
  return (dispatch, getState) => {
    const state = getState()
    if (state.tenantStatus.isFetching && tenant.name === state.tenantStatus.tenant) {
      return Promise.resolve()
    }
    dispatch(requestTenantStatus(tenant.name))
    return fetchTenantStatus(tenant.apiPrefix)
      .then(response => dispatch(receiveTenantStatus(tenant.name, response.data)))
      .catch(error => dispatch(failedTenantStatus(tenant.name, error)))
  }
}

export function clearTenantStatusAction () {
  return (dispatch) => {
    dispatch({type: TENANT_STATUS_CLEAR})
  }
}
