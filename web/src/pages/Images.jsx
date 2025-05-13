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
import { fetchImages, fetchImagesIfNeeded } from '../actions/images'
import ImageTable from '../containers/provider/ImageTable'
import { ReloadButton } from '../containers/Fetching'

function ImagesPage() {
  const tenant = useSelector((state) => state.tenant)
  const images = useSelector((state) => state.images.images[tenant.name])
  const isFetching = useSelector((state) => state.status.isFetching)
  const darkMode = useSelector((state) => state.preferences.darkMode)
  const dispatch = useDispatch()

  useEffect(() => {
    document.title = 'Zuul Images'
    dispatch(fetchImagesIfNeeded(tenant))
  }, [tenant, dispatch])

  console.log(images)

  return (
    <>
      <PageSection variant={darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
        <Level>
          <LevelItem>
          </LevelItem>
          <LevelItem>
            <ReloadButton
              isReloading={isFetching}
              reloadCallback={() => {dispatch(fetchImages(tenant))}}
            />
          </LevelItem>
        </Level>
        <Title headingLevel="h2">
          Images
        </Title>
        <ImageTable
          images={images}
          fetching={isFetching}
          linkPrefix={`${tenant.linkPrefix}/image`}
        />
      </PageSection>
    </>
  )
}

export default withRouter(ImagesPage)
