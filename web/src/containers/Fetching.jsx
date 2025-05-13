// Copyright 2020 BMW Group
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

import {
  Button,
  Title,
  EmptyState,
  EmptyStateVariant,
  Spinner,
} from '@patternfly/react-core'

import { SyncAltIcon, SyncIcon } from '@patternfly/react-icons'

function ReloadButton({ isReloading, reloadCallback }) {
  return (
    <span
      className="zuul-reload-button"
      onClick={() => reloadCallback()}
    >
      <Button
        variant="plain"
        isInline
        icon={<SyncAltIcon />}
        isLoading={isReloading}
      />
      {isReloading ? 'Reloading' : 'Reload'}
    </span>
  )
}

ReloadButton.propTypes = {
  isReloading: PropTypes.bool.isRequired,
  reloadCallback: PropTypes.func.isRequired,
}

function Fetchable(props) {
  const { isFetching, fetchCallback } = props
  let content = null

  if (isFetching) {
    content = (
      <div>
        <Spinner size="md" />
      </div>
    )
  } else {
    content = (
      <Button
        variant="link"
        isInline icon={<SyncIcon />}
        onClick={() => {fetchCallback({force: true})}}
        style={{textDecoration: 'none'}}
      >
        refresh
      </Button>
    )
  }

  return (
    <div style={{float: 'right'}}>
      {content}
    </div>
  )
}

Fetchable.propTypes = {
  isFetching: PropTypes.bool,
  fetchCallback: PropTypes.func,
}

function Fetching() {
  return (
    <EmptyState variant={EmptyStateVariant.small}>
      <Spinner />
      <Title headingLevel="h4" size="lg">
        Fetching info...
      </Title>
    </EmptyState>
  )
}

export { Fetchable, Fetching, ReloadButton }
