// Copyright 2018 Red Hat, Inc
// Copyright 2025 Acme Gating, LLC
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
  NODESET_REQUESTS_FETCH_FAIL,
  NODESET_REQUESTS_FETCH_REQUEST,
  NODESET_REQUESTS_FETCH_SUCCESS
} from '../actions/nodesetRequests'

export default (state = {
  receivedAt: 0,
  isFetching: false,
  requests: [],
}, action) => {
  switch (action.type) {
    case NODESET_REQUESTS_FETCH_REQUEST:
      return {
        ...state,
        isFetching: true,
      }
    case NODESET_REQUESTS_FETCH_SUCCESS:
      return {
        ...state,
        isFetching: false,
        requests: action.requests,
        receivedAt: action.receivedAt,
      }
    case NODESET_REQUESTS_FETCH_FAIL:
      return {
        ...state,
        isFetching: false
      }
    default:
      return state
  }
}
