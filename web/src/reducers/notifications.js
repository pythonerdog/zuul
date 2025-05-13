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
  ADD_NOTIFICATION,
  CLEAR_NOTIFICATION,
  CLEAR_NOTIFICATIONS,
  addApiError,
} from '../actions/notifications'


export default (state = [], action) => {
  // Intercept API failure
  // TODO: Are these still used?
  if (action.notification && action.type.match(/.*_FETCH_FAIL$/)) {
    action = addApiError(action.notification)
  }
  // Intercept Admin API failures
  if (action.notification && action.type.match(/ADMIN_.*_FAIL$/)) {
    action = addApiError(action.notification)
  }
  switch (action.type) {
    case ADD_NOTIFICATION:
      if (state.filter(notification => (
        notification.url === action.notification.url &&
        notification.status === action.notification.status)).length > 0)
        return state
      return [
        ...state,
        { ...action.notification, id: action.id, date: Date.now() }]
    case CLEAR_NOTIFICATION:
      return state.filter(item => (item.id !== action.id))
    case CLEAR_NOTIFICATIONS:
      return []
    default:
      return state
  }
}
