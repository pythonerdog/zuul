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

export const IMAGES_FETCH_REQUEST = 'IMAGES_FETCH_REQUEST'
export const IMAGES_FETCH_SUCCESS = 'IMAGES_FETCH_SUCCESS'
export const IMAGES_FETCH_FAIL = 'IMAGES_FETCH_FAIL'

export const requestImages = () => ({
  type: IMAGES_FETCH_REQUEST
})

export const receiveImages = (tenant, json) => ({
  type: IMAGES_FETCH_SUCCESS,
  tenant: tenant,
  images: json,
  receivedAt: Date.now()
})

const failedImages = error => ({
  type: IMAGES_FETCH_FAIL,
  error
})

export const fetchImages = (tenant) => dispatch => {
  dispatch(requestImages())
  return API.fetchImages(tenant.apiPrefix)
    .then(response => dispatch(receiveImages(tenant.name, response.data)))
    .catch(error => dispatch(failedImages(error)))
}

const shouldFetchImages = (tenant, state) => {
  const images = state.images.images[tenant.name]
  if (!images) {
    return true
  }
  if (images.isFetching) {
    return false
  }
  return false
}

export const fetchImagesIfNeeded = (tenant) => (dispatch, getState) => {
  if (shouldFetchImages(tenant, getState())) {
    return dispatch(fetchImages(tenant))
  }
  return Promise.resolve()
}
