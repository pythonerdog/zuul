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

import * as API from '../api'

export const LOGFILE_FETCH_REQUEST = 'LOGFILE_FETCH_REQUEST'
export const LOGFILE_FETCH_SUCCESS = 'LOGFILE_FETCH_SUCCESS'
export const LOGFILE_FETCH_FAIL = 'LOGFILE_FETCH_FAIL'

export const requestLogfile = (url) => ({
  type: LOGFILE_FETCH_REQUEST,
  url: url,
})

const SYSLOGDATE = '\\w+\\s+\\d+\\s+\\d{2}:\\d{2}:\\d{2}((\\.|\\,)\\d{3,6})?'
const DATEFMT = '\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}((\\.|\\,)\\d{3,6})?'
const STATUSFMT = '(DEBUG|INFO|WARNING|ERROR|TRACE|AUDIT|CRITICAL)'

const severityMap = {
  DEBUG: 1,
  INFO: 2,
  WARNING: 3,
  ERROR: 4,
  TRACE: 5,
  AUDIT: 6,
  CRITICAL: 7,
}

const OSLO_LOGMATCH = new RegExp(`^(${DATEFMT})(( \\d+)? (${STATUSFMT}).*)`)
const SYSTEMD_LOGMATCH = new RegExp(`^(${SYSLOGDATE})( (\\S+) \\S+\\[\\d+\\]\\: (${STATUSFMT}).*)`)

const receiveLogfile = (buildId, file, data) => {

  const out = data.split(/\r?\n/).map((line, idx) => {
    let m = null
    let sev = null

    m = SYSTEMD_LOGMATCH.exec(line)
    if (m) {
      sev = severityMap[m[7]]
    } else {
      OSLO_LOGMATCH.exec(line)
      if (m) {
        sev = severityMap[m[7]]
      }
    }

    return {
      text: line,
      index: idx+1,
      severity: sev
    }
  })
  return {
    type: LOGFILE_FETCH_SUCCESS,
    buildId,
    fileName: file,
    fileContent: out,
    receivedAt: Date.now()
  }
}

const failedLogfile = (error, url) => {
  error.url = url
  return {
    type: LOGFILE_FETCH_FAIL,
    error
  }
}

export function fetchLogfile(buildId, file, state) {
  return async function (dispatch) {
    // Don't do anything if the logfile is already part of our local state
    if (
      buildId in state.logfile.files &&
      file in state.logfile.files[buildId]
    ) {
      return Promise.resolve()
    }
    // Since this method is only called after fetchBuild() and fetchManifest(),
    // we can assume both are there.
    const build = state.build.builds[buildId]
    const manifest = state.build.manifests[buildId]
    const item = manifest.index['/' + file]

    if (!item) {
      return dispatch(
        failedLogfile(Error(`No manifest entry found for logfile "${file}"`))
      )
    }

    if (item.mimetype !== 'text/plain') {
      return dispatch(
        failedLogfile(Error(`Logfile "${file}" has invalid mimetype`))
      )
    }

    const url = build.log_url + file
    dispatch(requestLogfile())
    try {
      const auth_log_request = state.info.capabilities?.auth?.auth_log_file_requests === true
      const response = await API.getLogFile(url, auth_log_request, { transformResponse: [] })
      dispatch(receiveLogfile(buildId, file, response.data))
    } catch(error) {
      dispatch(failedLogfile(error, url))
    }
  }
}
