// Copyright 2021 BMW Group
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

import * as types from './actionTypes'
import * as API from '../api'

function requestComponents() {
  return { type: types.COMPONENTS_FETCH_REQUEST }
}

function receiveComponents(components) {
  return { type: types.COMPONENTS_FETCH_SUCCESS, components }
}

function failedComponents(error) {
  return { type: types.COMPONENTS_FETCH_FAIL, error }
}

export function fetchComponents() {
  return async function (dispatch) {
    dispatch(requestComponents())
    try {
      const response = await API.fetchComponents()
      dispatch(receiveComponents(response.data))
    } catch (error) {
      dispatch(failedComponents(error))
    }
  }
}
