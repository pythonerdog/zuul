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
import SwaggerUi from 'swagger-ui'
import 'swagger-ui/dist/swagger-ui.css'
import { PageSection, PageSectionVariants } from '@patternfly/react-core'

import { fetchOpenApiIfNeeded } from '../actions/openapi'


class OpenApiPage extends React.Component {
  static propTypes = {
    tenant: PropTypes.object,
    remoteData: PropTypes.object,
    dispatch: PropTypes.func,
    preferences: PropTypes.object,
  }

  updateData = (force) => {
    this.props.dispatch(fetchOpenApiIfNeeded(force))
  }

  componentDidMount () {
    document.title = 'Zuul API'
    this.updateData()
  }

  componentDidUpdate (prevProps) {
    if (this.props.remoteData.openapi &&
        this.props.remoteData.openapi !== prevProps.remoteData.openapi) {
      SwaggerUi({
        dom_id: '#swaggerContainer',
        spec: this.props.remoteData.openapi,
        presets: [SwaggerUi.presets.apis]
      })
    }
  }

  render() {
    return (
      <PageSection variant={this.props.preferences.darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
        <div id="swaggerContainer" />
      </PageSection>
    )
  }
}

export default connect(state => ({
  tenant: state.tenant,
  remoteData: state.openapi,
  preferences: state.preferences,
}))(OpenApiPage)
