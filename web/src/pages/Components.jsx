// Copyright 2021 BMW Group
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
  EmptyState,
  EmptyStateVariant,
  EmptyStateIcon,
  PageSection,
  PageSectionVariants,
  Text,
  TextContent,
  Title,
} from '@patternfly/react-core'
import { ServiceIcon } from '@patternfly/react-icons'

import { fetchComponents } from '../actions/component'
import { Fetching } from '../containers/Fetching'
import ComponentTable from '../containers/component/ComponentTable'

function ComponentsPage({ components, isFetching, fetchComponents }) {
  useEffect(() => {
    document.title = 'Zuul Components'
    fetchComponents()
  }, [fetchComponents])

  // TODO (felix): Let the table handle the empty state and the fetching,
  // similar to the builds table.
  const content =
    components === undefined || isFetching ? (
      <Fetching />
    ) : Object.keys(components).length === 0 ? (
      <EmptyState variant={EmptyStateVariant.small}>
        <EmptyStateIcon icon={ServiceIcon} />
        <Title headingLevel="h4" size="lg">
          It looks like no components are connected to ZooKeeper
        </Title>
      </EmptyState>
    ) : (
      <ComponentTable components={components} />
    )

  return (
    <>
      <PageSection variant={PageSectionVariants.light}>
        <TextContent>
          <Text component="h1">Components</Text>
          <Text component="p">
            This page shows all Zuul components and their current state.
          </Text>
        </TextContent>
        {content}
      </PageSection>
    </>
  )
}

ComponentsPage.propTypes = {
  components: PropTypes.object.isRequired,
  isFetching: PropTypes.bool.isRequired,
  fetchComponents: PropTypes.func.isRequired,
}

function mapStateToProps(state) {
  return {
    components: state.component.components,
    isFetching: state.component.isFetching,
  }
}

const mapDispatchToProps = { fetchComponents }

export default connect(mapStateToProps, mapDispatchToProps)(ComponentsPage)
