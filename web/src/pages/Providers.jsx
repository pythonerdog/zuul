// Copyright 2024 Acme Gating, LLC
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
import { useSelector, useDispatch } from 'react-redux'
import { withRouter } from 'react-router-dom'
import {
  Level,
  LevelItem,
  PageSection,
  PageSectionVariants,
  Title,
} from '@patternfly/react-core'
import { fetchProviders, fetchProvidersIfNeeded } from '../actions/providers'
import ProviderTable from '../containers/provider/ProviderTable'
import { ReloadButton } from '../containers/Fetching'

function ProvidersPage() {
  const tenant = useSelector((state) => state.tenant)
  const providers = useSelector((state) => state.providers.providers[tenant.name])
  const isFetching = useSelector((state) => state.status.isFetching)
  const darkMode = useSelector((state) => state.preferences.darkMode)
  const dispatch = useDispatch()

  useEffect(() => {
    document.title = 'Zuul Providers'
    dispatch(fetchProvidersIfNeeded(tenant))
  }, [tenant, dispatch])

  return (
    <>
      <PageSection variant={darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
        <Level>
          <LevelItem>
          </LevelItem>
          <LevelItem>
            <ReloadButton
              isReloading={isFetching}
              reloadCallback={() => {dispatch(fetchProviders(tenant))}}
            />
          </LevelItem>
        </Level>
        <Title headingLevel="h2">
          Providers
        </Title>
        <ProviderTable
          providers={providers}
          fetching={isFetching} />
      </PageSection>
    </>
  )
}

export default withRouter(ProvidersPage)
