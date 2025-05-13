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

import React, { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import { useHistory, useLocation } from 'react-router-dom'
import {
  PageSection,
  PageSectionVariants,
  Text,
  TextContent,
} from '@patternfly/react-core'
import ReactJson from 'react-json-view'

import FreezeJobToolbar from '../containers/freezejob/FreezeJobToolbar'
import { makeFreezeJobKey, fetchFreezeJobIfNeeded } from '../actions/freezejob'

function FreezeJobPage(props) {
  const { tenant, fetchFreezeJobIfNeeded } = props

  const [currentPipeline, setCurrentPipeline] = useState()
  const [currentProject, setCurrentProject] = useState()
  const [currentBranch, setCurrentBranch] = useState()
  const [currentJob, setCurrentJob] = useState()
  const history = useHistory()
  const location = useLocation()

  if (!currentBranch) {
    const urlParams = new URLSearchParams(location.search)
    const pipeline = urlParams.get('pipeline')
    const project = urlParams.get('project')
    const branch = urlParams.get('branch')
    const job = urlParams.get('job')
    if (pipeline && branch && project && job) {
      setCurrentPipeline(pipeline)
      setCurrentProject(project)
      setCurrentBranch(branch)
      setCurrentJob(job)
    }
  }

  useEffect(() => {
    document.title = 'Zuul Frozen Job'
    if (currentPipeline && currentProject && currentBranch && currentJob) {
      fetchFreezeJobIfNeeded(tenant, currentPipeline, currentProject,
                             currentBranch, currentJob)
    }
  }, [fetchFreezeJobIfNeeded, tenant, currentPipeline, currentProject,
      currentBranch, currentJob])

  function onChange(pipeline, project, branch, job) {
    setCurrentPipeline(pipeline)
    setCurrentProject(project)
    setCurrentBranch(branch)
    setCurrentJob(job)

    const searchParams = new URLSearchParams('')
    searchParams.append('pipeline', pipeline)
    searchParams.append('project', project)
    searchParams.append('branch', branch)
    searchParams.append('job', job)
    history.push({
      pathname: location.pathname,
      search: searchParams.toString(),
    })

    if (currentPipeline && currentProject && currentBranch && currentJob) {
      fetchFreezeJobIfNeeded(tenant, currentPipeline, currentProject,
                             currentBranch, currentJob)
    }
  }

  const tenantJobs = props.freezejob.freezeJobs[tenant.name]
  const freezeJobKey = makeFreezeJobKey(currentPipeline,
                                        currentProject,
                                        currentBranch,
                                        currentJob)
  const job = tenantJobs ? tenantJobs[freezeJobKey] : undefined
  function renderFrozenJob() {
    return (
      <span style={{whiteSpace: 'pre-wrap'}}>
        <ReactJson
          src={job}
          name={null}
          collapsed={false}
          sortKeys={true}
          enableClipboard={false}
          displayDataTypes={false}
          theme={props.preferences.darkMode ? 'tomorrow' : 'rjv-default'}/>
      </span>
    )
  }

  return (
    <>
      <PageSection variant={PageSectionVariants.light}>
        <TextContent>
          <Text component="h1">Freeze Job</Text>
          <Text component="p">
            Freezing a job asks Zuul to combine all the
            <i>project</i> and <i>job</i> configuration
            stanzas for a job as if a change for a given
            project and branch were to be enqueued into
            a specific pipeline.  The resulting job
            configuration is displayed below.
          </Text>
        </TextContent>
        <FreezeJobToolbar
          onChange={onChange}
          defaultPipeline={currentPipeline}
          defaultProject={currentProject}
          defaultBranch={currentBranch}
          defaultJob={currentJob}
        />
        {job && renderFrozenJob(job)}
      </PageSection>
    </>
  )
}

FreezeJobPage.propTypes = {
  fetchFreezeJobIfNeeded: PropTypes.func,
  tenant: PropTypes.object,
  freezejob: PropTypes.object,
  preferences: PropTypes.object,
}

function mapStateToProps(state) {
  return {
    tenant: state.tenant,
    freezejob: state.freezejob,
    preferences: state.preferences,
  }
}

const mapDispatchToProps = {
  fetchFreezeJobIfNeeded
}

export default connect(mapStateToProps, mapDispatchToProps)(FreezeJobPage)
