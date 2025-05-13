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

import * as React from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import { PageSection, PageSectionVariants } from '@patternfly/react-core'

import { fetchJobsIfNeeded } from '../actions/jobs'
import { Fetchable } from '../containers/Fetching'
import Jobs from '../containers/jobs/Jobs'


class JobsPage extends React.Component {
  static propTypes = {
    tenant: PropTypes.object,
    remoteData: PropTypes.object,
    dispatch: PropTypes.func,
    preferences: PropTypes.object,
  }

  updateData = (force) => {
    this.props.dispatch(fetchJobsIfNeeded(this.props.tenant, force))
  }

  componentDidMount () {
    document.title = 'Zuul Jobs'
    if (this.props.tenant.name) {
      this.updateData()
    }
  }

  componentDidUpdate (prevProps) {
    if (this.props.tenant.name !== prevProps.tenant.name) {
      this.updateData()
    }
  }

  render () {
    const { remoteData } = this.props

    const jobs = remoteData.jobs[this.props.tenant.name]
    return (
      <PageSection variant={this.props.preferences.darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
        <PageSection variant={PageSectionVariants.light} style={{paddingRight: '5px'}}>
          <Fetchable
            isFetching={remoteData.isFetching}
            fetchCallback={this.updateData}
          />
        </PageSection>
        {jobs && jobs.length > 0 &&
          <Jobs
            jobs={jobs}
          />}
      </PageSection>
    )
  }
}

export default connect(state => ({
  tenant: state.tenant,
  remoteData: state.jobs,
  preferences: state.preferences,
}))(JobsPage)
