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

export const AUTH_CONFIG_REQUEST = 'AUTH_CONFIG_REQUEST'
export const AUTH_CONFIG_SUCCESS = 'AUTH_CONFIG_SUCCESS'
export const AUTH_CONFIG_FAIL = 'AUTH_CONFIG_FAIL'

export const USER_ACL_REQUEST = 'USER_ACL_REQUEST'
export const USER_ACL_SUCCESS = 'USER_ACL_SUCCESS'
export const USER_ACL_FAIL = 'USER_ACL_FAIL'

export const AUTH_START = 'AUTH_START'

const authConfigRequest = () => ({
  type: AUTH_CONFIG_REQUEST
})

function createAuthParamsFromJson(json) {
  let auth_info = json.info.capabilities.auth

  let auth_params = {
    authority: '',
    client_id: '',
    scope: '',
    loadUserInfo: true,
  }
  if (!auth_info) {
    console.log('No auth config')
    return auth_params
  }
  const realm = auth_info.default_realm
  const client_config = auth_info.realms[realm]
  if (client_config && client_config.driver === 'OpenIDConnect') {
    auth_params.client_id = client_config.client_id
    auth_params.scope = client_config.scope
    auth_params.authority = client_config.authority
    auth_params.loadUserInfo = client_config.load_user_info
    return auth_params
  } else {
    console.log('No OpenIDConnect provider found')
    return auth_params
  }
}

const authConfigSuccess = (json, auth_params) => ({
  type: AUTH_CONFIG_SUCCESS,
  info: json.info.capabilities.auth,
  auth_params: auth_params,
})

const authConfigFail = error => ({
    type: AUTH_CONFIG_FAIL,
    error
})

export const configureAuthFromTenant = (tenantName) => (dispatch) => {
  dispatch(authConfigRequest())
  return API.fetchTenantInfo('tenant/' + tenantName + '/')
    .then(response => {
      dispatch(authConfigSuccess(
        response.data,
        createAuthParamsFromJson(response.data)))
    })
    .catch(error => {
      dispatch(authConfigFail(error))
    })
}

export const configureAuthFromInfo = (info) => (dispatch) => {
  try {
    dispatch(authConfigSuccess(
      {info: info},
      createAuthParamsFromJson({info: info})))
  } catch(error) {
      dispatch(authConfigFail(error))
  }
}
