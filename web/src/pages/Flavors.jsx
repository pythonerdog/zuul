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
import { fetchFlavors, fetchFlavorsIfNeeded } from '../actions/flavors'
import FlavorTable from '../containers/provider/FlavorTable'
import { ReloadButton } from '../containers/Fetching'

function FlavorsPage() {
  const tenant = useSelector((state) => state.tenant)
  const flavors = useSelector((state) => state.flavors.flavors[tenant.name])
  const isFetching = useSelector((state) => state.status.isFetching)
  const darkMode = useSelector((state) => state.preferences.darkMode)
  const dispatch = useDispatch()

  useEffect(() => {
    document.title = 'Zuul Flavors'
    dispatch(fetchFlavorsIfNeeded(tenant))
  }, [tenant, dispatch])

  console.log(flavors)

  return (
    <>
      <PageSection variant={darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
        <Level>
          <LevelItem>
          </LevelItem>
          <LevelItem>
            <ReloadButton
              isReloading={isFetching}
              reloadCallback={() => {dispatch(fetchFlavors(tenant))}}
            />
          </LevelItem>
        </Level>
        <Title headingLevel="h2">
          Flavors
        </Title>
        <FlavorTable
          flavors={flavors}
          fetching={isFetching}
          linkPrefix={`${tenant.linkPrefix}/flavor`}
        />
      </PageSection>
    </>
  )
}

export default withRouter(FlavorsPage)
