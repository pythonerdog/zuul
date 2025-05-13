// Copyright 2020 Red Hat, Inc
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

export const ADMIN_DEQUEUE_FAIL = 'ADMIN_DEQUEUE_FAIL'
export const ADMIN_ENQUEUE_FAIL = 'ADMIN_ENQUEUE_FAIL'
export const ADMIN_AUTOHOLD_FAIL = 'ADMIN_AUTOHOLD_FAIL'
export const ADMIN_PROMOTE_FAIL = 'ADMIN_PROMOTE_FAIL'

function parseAPIerror(error) {
  if (error.response) {
    let parser = new DOMParser()
    let htmlError = parser.parseFromString(error.response.data, 'text/html')
    let error_description = htmlError.getElementsByTagName('p')[0].innerText
    return (error_description)
  } else {
    return (error)
  }
}

export const addDequeueError = error => ({
  type: ADMIN_DEQUEUE_FAIL,
  notification: parseAPIerror(error)
})

export const addEnqueueError = error => ({
  type: ADMIN_ENQUEUE_FAIL,
  notification: parseAPIerror(error)
})

export const addAutoholdError = error => ({
  type: ADMIN_AUTOHOLD_FAIL,
  notification: parseAPIerror(error)
})

export const addPromoteError = error => ({
  type: ADMIN_PROMOTE_FAIL,
  notification: parseAPIerror(error)
})