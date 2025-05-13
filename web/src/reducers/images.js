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
  IMAGES_FETCH_FAIL,
  IMAGES_FETCH_REQUEST,
  IMAGES_FETCH_SUCCESS
} from '../actions/images'

export default (state = {
  isFetching: false,
  images: {},
}, action) => {
  switch (action.type) {
    case IMAGES_FETCH_REQUEST:
      return {
        isFetching: true,
        images: state.images,
      }
    case IMAGES_FETCH_SUCCESS:
      return {
        isFetching: false,
        images: {
          ...state.images,
          [action.tenant]: action.images
        }
      }
    case IMAGES_FETCH_FAIL:
      return {
        isFetching: false,
        images: state.images,
      }
    default:
      return state
  }
}
