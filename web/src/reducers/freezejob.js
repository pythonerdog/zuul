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
  FREEZE_JOB_FETCH_FAIL,
  FREEZE_JOB_FETCH_REQUEST,
  FREEZE_JOB_FETCH_SUCCESS
} from '../actions/freezejob'

export default (state = {
  isFetching: false,
  freezeJobs: {},
}, action) => {
  let stateFreezeJobs
  switch (action.type) {
    case FREEZE_JOB_FETCH_REQUEST:
      return {
        isFetching: true,
        freezeJobs: state.freezeJobs,
      }
    case FREEZE_JOB_FETCH_SUCCESS:
      stateFreezeJobs = !state.freezeJobs[action.tenant] ?
        { ...state.freezeJobs, [action.tenant]: {} } :
        { ...state.freezeJobs }
      return {
        isFetching: false,
        freezeJobs: {
          ...stateFreezeJobs,
          [action.tenant]: {
            ...stateFreezeJobs[action.tenant],
            [action.freezeJobKey]: action.freezeJob
          }
        }
      }
    case FREEZE_JOB_FETCH_FAIL:
      return {
        isFetching: false,
        freezeJobs: state.freezeJobs,
      }
    default:
      return state
  }
}
