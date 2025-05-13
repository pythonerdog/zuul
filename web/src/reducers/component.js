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

import * as types from '../actions/actionTypes'
import initialState from './initialState'

export default (state = initialState.component, action) => {
  switch (action.type) {
    case types.COMPONENTS_FETCH_REQUEST:
      return { ...state, isFetching: true }
    case types.COMPONENTS_FETCH_SUCCESS:
      return { ...state, components: action.components, isFetching: false }
    case types.COMPONENTS_FETCH_FAIL:
      return { ...state, components: {}, isFetching: false }
    default:
      return state
  }
}
