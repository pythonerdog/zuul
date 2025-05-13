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

import {
  FLAVORS_FETCH_FAIL,
  FLAVORS_FETCH_REQUEST,
  FLAVORS_FETCH_SUCCESS
} from '../actions/flavors'

export default (state = {
  isFetching: false,
  flavors: {},
}, action) => {
  switch (action.type) {
    case FLAVORS_FETCH_REQUEST:
      return {
        isFetching: true,
        flavors: state.flavors,
      }
    case FLAVORS_FETCH_SUCCESS:
      return {
        isFetching: false,
        flavors: {
          ...state.flavors,
          [action.tenant]: action.flavors
        }
      }
    case FLAVORS_FETCH_FAIL:
      return {
        isFetching: false,
        flavors: state.flavors,
      }
    default:
      return state
  }
}
