// Copyright 2018 Red Hat, Inc
// Copyright 2022 Acme Gating, LLC
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
  JOB_GRAPH_FETCH_FAIL,
  JOB_GRAPH_FETCH_REQUEST,
  JOB_GRAPH_FETCH_SUCCESS
} from '../actions/jobgraph'

export default (state = {
  isFetching: false,
  jobGraphs: {},
}, action) => {
  let stateJobGraphs
  switch (action.type) {
    case JOB_GRAPH_FETCH_REQUEST:
      return {
        isFetching: true,
        jobGraphs: state.jobGraphs,
      }
    case JOB_GRAPH_FETCH_SUCCESS:
      stateJobGraphs = !state.jobGraphs[action.tenant] ?
        { ...state.jobGraphs, [action.tenant]: {} } :
        { ...state.jobGraphs }
      return {
        isFetching: false,
        jobGraphs: {
          ...stateJobGraphs,
          [action.tenant]: {
            ...stateJobGraphs[action.tenant],
            [action.jobGraphKey]: action.jobGraph
          }
        }
      }
    case JOB_GRAPH_FETCH_FAIL:
      return {
        isFetching: false,
        jobGraphs: state.jobGraphs,
      }
    default:
      return state
  }
}
