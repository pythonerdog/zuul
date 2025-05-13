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

import React, { useEffect } from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'

import {
  Title,
} from '@patternfly/react-core'
import { PageSection, PageSectionVariants } from '@patternfly/react-core'

import { fetchSemaphoresIfNeeded } from '../actions/semaphores'
import Semaphore from '../containers/semaphore/Semaphore'

function SemaphorePage({ match, semaphores, tenant, fetchSemaphoresIfNeeded, isFetching, preferences }) {

  const semaphoreName = match.params.semaphoreName

  useEffect(() => {
    document.title = `Zuul Semaphore | ${semaphoreName}`
    fetchSemaphoresIfNeeded(tenant, true)
  }, [fetchSemaphoresIfNeeded, tenant, semaphoreName])

  const semaphore = semaphores[tenant.name] ? semaphores[tenant.name].find(
    e => e.name === semaphoreName) : undefined

  return (
    <PageSection variant={preferences.darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
      <Title headingLevel="h2">
        Details for Semaphore <span style={{color: 'var(--pf-global--primary-color--100)'}}>{semaphoreName}</span>
      </Title>

      <Semaphore semaphore={semaphore}
                 fetching={isFetching} />
    </PageSection>
  )
}

SemaphorePage.propTypes = {
  match: PropTypes.object.isRequired,
  semaphores: PropTypes.object.isRequired,
  tenant: PropTypes.object.isRequired,
  isFetching: PropTypes.bool.isRequired,
  fetchSemaphoresIfNeeded: PropTypes.func.isRequired,
  preferences: PropTypes.object,
}
const mapDispatchToProps = { fetchSemaphoresIfNeeded }

function mapStateToProps(state) {
  return {
    tenant: state.tenant,
    semaphores: state.semaphores.semaphores,
    isFetching: state.semaphores.isFetching,
    preferences: state.preferences,
  }
}

export default connect(mapStateToProps, mapDispatchToProps)(SemaphorePage)
