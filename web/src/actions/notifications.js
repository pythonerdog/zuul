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

export const ADD_NOTIFICATION = 'ADD_NOTIFICATION'
export const CLEAR_NOTIFICATION = 'CLEAR_NOTIFICATION'
export const CLEAR_NOTIFICATIONS = 'CLEAR_NOTIFICATIONS'

let notificationId = 0

export const addNotification = notification => ({
  type: ADD_NOTIFICATION,
  id: notificationId++,
  notification
})

export const addApiError = error => {
  const d = {
    url: (error && error.request && error.request.responseURL) || error.url,
    type: 'error',
  }
  if (error.response) {
    d.text = error.response.statusText
    d.status = error.response.status
  } else {
    d.status = 'Unable to fetch URL, check your network connectivity,'
      + ' browser plugins, ad-blockers, or try to refresh this page'
    d.text = error.message
  }
  return addNotification(d)
}

export const clearNotification = id => ({
  type: CLEAR_NOTIFICATION,
  id
})

export const clearNotifications = () => ({
  type: CLEAR_NOTIFICATIONS
})
