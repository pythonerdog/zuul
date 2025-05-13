// Copyright 2021 BMW Group
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

import React, { useEffect } from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import {
  PageSection,
  PageSectionVariants,
} from '@patternfly/react-core'

import { fetchSemaphoresIfNeeded } from '../actions/semaphores'
import SemaphoreTable from '../containers/semaphore/SemaphoreTable'

function SemaphoresPage({ tenant, semaphores, isFetching, fetchSemaphoresIfNeeded }) {
  useEffect(() => {
    document.title = 'Zuul Semaphores'
    fetchSemaphoresIfNeeded(tenant, true)
  }, [fetchSemaphoresIfNeeded, tenant])

  return (
    <>
      <PageSection variant={PageSectionVariants.light}>
        <SemaphoreTable
          semaphores={semaphores[tenant.name]}
          fetching={isFetching} />
      </PageSection>
    </>
  )
}

SemaphoresPage.propTypes = {
  tenant: PropTypes.object.isRequired,
  semaphores: PropTypes.object.isRequired,
  isFetching: PropTypes.bool.isRequired,
  fetchSemaphoresIfNeeded: PropTypes.func.isRequired,
}

function mapStateToProps(state) {
  return {
    tenant: state.tenant,
    semaphores: state.semaphores.semaphores,
    isFetching: state.semaphores.isFetching,
  }
}

const mapDispatchToProps = { fetchSemaphoresIfNeeded }

export default connect(mapStateToProps, mapDispatchToProps)(SemaphoresPage)
