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
  LOGFILE_FETCH_FAIL,
  LOGFILE_FETCH_REQUEST,
  LOGFILE_FETCH_SUCCESS,
} from '../actions/logfile'

import initialState from './initialState'

export default (state = initialState.logfile, action) => {
  switch (action.type) {
    case LOGFILE_FETCH_REQUEST:
      return { ...state, isFetching: true, url: action.url }
    case LOGFILE_FETCH_SUCCESS: {
      let filesForBuild = state.files[action.buildId] || {}
      filesForBuild = {
        ...filesForBuild,
        [action.fileName]: action.fileContent,
      }
      return {
        ...state,
        isFetching: false,
        files: { ...state.files, [action.buildId]: filesForBuild },
      }
    }
    case LOGFILE_FETCH_FAIL:
      return { ...state, isFetching: false }
    default:
      return state
  }
}
