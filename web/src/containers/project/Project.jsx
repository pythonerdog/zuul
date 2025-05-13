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

import React, { useState } from 'react'
import PropTypes from 'prop-types'
import {
  Tabs,
  Tab,
} from '@patternfly/react-core'

import ProjectVariant from './ProjectVariant'


function Project(props) {
  const [variantIdx, setVariantIdx] = useState(0)
  const { project } = props

  function renderVariantTitle (variant) {
    let title = variant.source_context.project === project.name ?
        variant.source_context.branch : variant.source_context.project
    return title
  }

  return (
    <React.Fragment>
      <Tabs activeKey={variantIdx}
            onSelect={(event, tabIndex) => setVariantIdx(tabIndex)}
            isBox>
        {project.configs.map((variant, idx) => (
          <Tab key={idx} eventKey={idx}
               title={renderVariantTitle(variant)}>
            <ProjectVariant variant={variant} />
          </Tab>
        ))}
      </Tabs>
    </React.Fragment>
  )
}

Project.propTypes = {
  project: PropTypes.object.isRequired,
}

export default Project
