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

import React, { useState } from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import { useHistory, useLocation } from 'react-router-dom'

import JobGraphToolbar from './JobGraphToolbar'
import JobGraphDisplay from './JobGraphDisplay'

function JobGraph(props) {
  const [currentPipeline, setCurrentPipeline] = useState()
  const [currentBranch, setCurrentBranch] = useState()
  const history = useHistory()
  const location = useLocation()

  if (!currentBranch) {
    const urlParams = new URLSearchParams(location.search)
    const branch = urlParams.get('branch')
    const pipeline = urlParams.get('pipeline')
    if (pipeline && branch) {
      setCurrentPipeline(pipeline)
      setCurrentBranch(branch)
    }
  }

  function onChange(pipeline, branch) {
    setCurrentPipeline(pipeline)
    setCurrentBranch(branch)

    const searchParams = new URLSearchParams('')
    searchParams.append('branch', branch)
    searchParams.append('pipeline', pipeline)
    history.push({
      pathname: location.pathname,
      search: searchParams.toString(),
    })
  }

  return (
    <>
      <JobGraphToolbar
        project={props.project}
        onChange={onChange}
        defaultBranch={currentBranch}
        defaultPipeline={currentPipeline}
      />
    {currentPipeline && currentBranch &&
      <JobGraphDisplay
        project={props.project}
        pipeline={currentPipeline}
        branch={currentBranch}
      />}
    </>
  )
}

JobGraph.propTypes = {
  project: PropTypes.object.isRequired,
  tenant: PropTypes.object,
  dispatch: PropTypes.func,
}

export default connect((state) => ({
  tenant: state.tenant,
}))(JobGraph)
