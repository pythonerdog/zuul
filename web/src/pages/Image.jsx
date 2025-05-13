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

import React, { useEffect, useMemo } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { withRouter } from 'react-router-dom'
import {
  Level,
  LevelItem,
  PageSection,
  PageSectionVariants,
  Title,
} from '@patternfly/react-core'
import PropTypes from 'prop-types'
import { fetchImages, fetchImagesIfNeeded } from '../actions/images'
import ImageDetail from '../containers/provider/ImageDetail'
import ImageBuildTable from '../containers/provider/ImageBuildTable'
import { ReloadButton } from '../containers/Fetching'

function ImagePage(props) {
  const imageName = props.match.params.imageName
  const tenant = useSelector((state) => state.tenant)
  const images = useSelector((state) => state.images.images[tenant.name])
  const isFetching = useSelector((state) => state.status.isFetching)
  const darkMode = useSelector((state) => state.preferences.darkMode)
  const dispatch = useDispatch()

  const image = useMemo(() =>
    images?images.find((e) => e.name === imageName):null,
    [images, imageName])

  useEffect(() => {
    document.title = 'Zuul Image'
    dispatch(fetchImagesIfNeeded(tenant))
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
              reloadCallback={() => {dispatch(fetchImages(tenant))}}
            />
          </LevelItem>
        </Level>
        <Title headingLevel="h2">
          Image {imageName}
        </Title>
        {image &&
         <>
           <ImageDetail image={image}/>
           {image.build_artifacts &&
            <ImageBuildTable
              buildArtifacts={image.build_artifacts}
              fetching={false}
            />
           }
         </>
        }
      </PageSection>
    </>
  )
}

ImagePage.propTypes = {
  match: PropTypes.object.isRequired,
}

export default withRouter(ImagePage)
