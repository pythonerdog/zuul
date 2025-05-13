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

import React, { useEffect, useMemo, useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { withRouter } from 'react-router-dom'
import {
  Level,
  LevelItem,
  PageSection,
  PageSectionVariants,
  Tab,
  Tabs,
  TabTitleText,
  Title,
} from '@patternfly/react-core'
import PropTypes from 'prop-types'
import { fetchProviders, fetchProvidersIfNeeded } from '../actions/providers'
import ProviderDetail from '../containers/provider/ProviderDetail'
import ImageTable from '../containers/provider/ImageTable'
import FlavorTable from '../containers/provider/FlavorTable'
import LabelTable from '../containers/provider/LabelTable'
import { ReloadButton } from '../containers/Fetching'

function ProviderPage(props) {
  const providerName = props.match.params.providerName
  const tenant = useSelector((state) => state.tenant)
  const providers = useSelector((state) => state.providers.providers[tenant.name])
  const isFetching = useSelector((state) => state.status.isFetching)
  const darkMode = useSelector((state) => state.preferences.darkMode)
  const dispatch = useDispatch()
  const [activeTabKey, setActiveTabKey] = useState('images')

  const provider = useMemo(() =>
    providers?providers.find((e) => e.name === providerName):null,
    [providers, providerName])

  useEffect(() => {
    document.title = 'Zuul Provider'
    dispatch(fetchProvidersIfNeeded(tenant))
  }, [tenant, dispatch])

  const handleTabClick = (event, tabIndex) => {
    setActiveTabKey(tabIndex)
  }

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
          Provider {providerName}
        </Title>
        {provider &&
         <>
           <ProviderDetail provider={provider}/>
           <Tabs activeKey={activeTabKey} onSelect={handleTabClick}>
             <Tab
               eventKey="images"
               title={<TabTitleText>Images</TabTitleText>}
             >
               {provider.images &&
                <ImageTable
                  images={provider.images}
                  fetching={false}
                  linkPrefix={`${tenant.linkPrefix}/provider/${providerName}/image`}/>
               }
             </Tab>
             <Tab
               eventKey="flavors"
               title={<TabTitleText>Flavors</TabTitleText>}
             >
               {provider.flavors &&
                <FlavorTable
                  flavors={provider.flavors}
                  fetching={false}/>
               }
             </Tab>
             <Tab
               eventKey="labels"
               title={<TabTitleText>Labels</TabTitleText>}
             >
               {provider.labels &&
                <LabelTable
                  labels={provider.labels}
                  fetching={false}/>
               }
             </Tab>
           </Tabs>
         </>
        }
      </PageSection>
    </>
  )
}

ProviderPage.propTypes = {
  match: PropTypes.object.isRequired,
}

export default withRouter(ProviderPage)
