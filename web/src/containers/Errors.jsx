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
import { Link } from 'react-router-dom'

import {
  Button,
  EmptyState,
  EmptyStateBody,
  EmptyStateIcon,
  EmptyStatePrimary,
  EmptyStateSecondaryActions,
  EmptyStateVariant,
  Title,
} from '@patternfly/react-core'

function EmptyPage(props) {
  const { title, icon, linkTarget, linkText } = props

  return (
    <EmptyState variant={EmptyStateVariant.small}>
      <EmptyStateIcon icon={icon} />
      <Title headingLevel="h4" size="lg">
        {title}
      </Title>
      <EmptyStatePrimary>
        <Link to={linkTarget}>
          <Button variant="link">{linkText}</Button>
        </Link>
      </EmptyStatePrimary>
    </EmptyState>
  )
}

EmptyPage.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.func.isRequired,
  linkTarget: PropTypes.string.isRequired,
  linkText: PropTypes.string.isRequired,
}

function EmptyBox(props) {
  const { title, icon, action, onAction, children } = props
  return (
    <EmptyState>
      <EmptyStateIcon icon={icon} />
      <Title headingLevel="h1">{title}</Title>
      <EmptyStateBody>
        {children}
      </EmptyStateBody>
      <EmptyStateSecondaryActions>
        <Button variant="link" onClick={onAction}>
          {action}
        </Button>
      </EmptyStateSecondaryActions>
    </EmptyState>
  )
}

EmptyBox.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.func.isRequired,
  action: PropTypes.string.isRequired,
  onAction: PropTypes.func.isRequired,
  children: PropTypes.node,
}


export { EmptyBox, EmptyPage }
