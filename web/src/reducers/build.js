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
  BUILD_FETCH_FAIL,
  BUILD_FETCH_REQUEST,
  BUILD_FETCH_SUCCESS,
  BUILDSET_FETCH_FAIL,
  BUILDSET_FETCH_REQUEST,
  BUILDSET_FETCH_SUCCESS,
  BUILD_OUTPUT_FAIL,
  BUILD_OUTPUT_REQUEST,
  BUILD_OUTPUT_SUCCESS,
  BUILD_OUTPUT_NOT_AVAILABLE,
  BUILD_MANIFEST_FAIL,
  BUILD_MANIFEST_REQUEST,
  BUILD_MANIFEST_SUCCESS,
  BUILD_MANIFEST_NOT_AVAILABLE,
} from '../actions/build'

import initialState from './initialState'

export default (state = initialState.build, action) => {
  switch (action.type) {
    case BUILD_FETCH_REQUEST:
    case BUILDSET_FETCH_REQUEST:
      return { ...state, isFetching: true }
    case BUILD_FETCH_SUCCESS:
      return {
        ...state,
        builds: { ...state.builds, [action.buildId]: action.build },
        isFetching: false,
      }
    case BUILDSET_FETCH_SUCCESS:
      return {
        ...state,
        buildsets: { ...state.buildsets, [action.buildsetId]: action.buildset },
        isFetching: false,
      }
    case BUILD_FETCH_FAIL:
      return {
        ...state,
        builds: { ...state.builds, [action.buildId]: null },
        isFetching: false,
      }
    case BUILDSET_FETCH_FAIL:
      return {
        ...state,
        buildsets: { ...state.buildsets, [action.buildsetId]: null },
        isFetching: false,
      }
    case BUILD_OUTPUT_REQUEST:
      return { ...state, isFetchingOutput: true }
    case BUILD_OUTPUT_SUCCESS:
      return {
        ...state,
        outputs: { ...state.outputs, [action.buildId]: action.output },
        errorIds: { ...state.errorIds, [action.buildId]: action.errorIds },
        hosts: { ...state.hosts, [action.buildId]: action.hosts },
        isFetchingOutput: false,
      }
    case BUILD_OUTPUT_FAIL:
    case BUILD_OUTPUT_NOT_AVAILABLE:
      return {
        ...state,
        outputs: { ...state.outputs, [action.buildId]: null },
        errorIds: { ...state.errorIds, [action.buildId]: null },
        hosts: { ...state.hosts, [action.buildId]: null },
        isFetchingOutput: false,
      }
    case BUILD_MANIFEST_REQUEST:
      return { ...state, isFetchingManifest: true }
    case BUILD_MANIFEST_SUCCESS:
      return {
        ...state,
        manifests: { ...state.manifests, [action.buildId]: action.manifest },
        isFetchingManifest: false,
      }
    case BUILD_MANIFEST_FAIL:
    case BUILD_MANIFEST_NOT_AVAILABLE:
      return {
        ...state,
        manifests: { ...state.manifests, [action.buildId]: null },
        isFetchingManifest: false,
      }
    default:
      return state
  }
}
