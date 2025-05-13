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

import {
  OPENAPI_FETCH_REQUEST,
  OPENAPI_FETCH_SUCCESS,
  OPENAPI_FETCH_FAIL,
} from '../actions/openapi'

export default (state = {
  isFetching: false,
  openapi: null,
}, action) => {
  switch (action.type) {
    case OPENAPI_FETCH_REQUEST:
    case OPENAPI_FETCH_FAIL:
      return {
        isFetching: true,
        tenant: state.openapi,
      }
    case OPENAPI_FETCH_SUCCESS:
      return {
        isFetching: false,
        openapi: action.openapi,
      }
    default:
      return state
  }
}
