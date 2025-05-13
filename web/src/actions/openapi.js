// Copyright 2018 Red Hat, Inc
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
import yaml from 'js-yaml'

export const OPENAPI_FETCH_REQUEST = 'OPENAPI_FETCH_REQUEST'
export const OPENAPI_FETCH_SUCCESS = 'OPENAPI_FETCH_SUCCESS'
export const OPENAPI_FETCH_FAIL    = 'OPENAPI_FETCH_FAIL'

export const fetchOpenApiRequest = () => ({
  type: OPENAPI_FETCH_REQUEST
})

export const fetchOpenApiSuccess = (yaml_data, whiteLabel) => {
  const data = yaml.safeLoad(yaml_data)
  if (whiteLabel) {
    const paths = {}
    for (let path in data.paths) {
      // Remove tenant list api
      if (path === '/api/tenants') {
        continue
      }
      // Remove tenant in path parameter
      data.paths[path].get.parameters.splice(0, 1)
      paths[path.replace('/api/tenant/{tenant}/', '/api/')] = data.paths[path]
    }
    data.paths = paths
  }
  data.servers = [{
    // Trim the trailing '/api/'
    url: API.apiUrl.substr(0, API.apiUrl.length - 5),
    description: 'Production server',
  }]
  return {
    type: OPENAPI_FETCH_SUCCESS,
    openapi: data,
  }
}

const fetchOpenApiFail = error => ({
  type: OPENAPI_FETCH_FAIL,
  error
})

const fetchOpenApi = (whiteLabel) => dispatch => {
  dispatch(fetchOpenApiRequest())
  return API.fetchOpenApi()
    .then(response => dispatch(fetchOpenApiSuccess(response.data, whiteLabel)))
    .catch(error => {
      dispatch(fetchOpenApiFail(error))
      setTimeout(() => {dispatch(fetchOpenApi())}, 5000)
    })
}

const shouldFetchOpenApi = openapi => {
  if (!openapi.openapi) {
    return true
  }
  if (openapi.isFetching) {
    return false
  }
  return true
}

export const fetchOpenApiIfNeeded = (force) => (dispatch, getState) => {
  const state = getState()
  if (force || shouldFetchOpenApi(state.openapi)) {
    return dispatch(fetchOpenApi(state.tenant.whiteLabel))
  }
}
