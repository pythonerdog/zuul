// Copyright 2020 Red Hat, Inc
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

import React from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import {
  EmptyState,
  EmptyStateBody,
  EmptyStateIcon,
  Spinner,
  Title,
  Label,
} from '@patternfly/react-core'
import {
  ResourcesFullIcon,
  TachometerAltIcon,
  LockIcon,
  TenantIcon,
  FingerprintIcon,
} from '@patternfly/react-icons'
import {
  Table,
  TableHeader,
  TableBody,
  TableVariant,
} from '@patternfly/react-table'
import { Link } from 'react-router-dom'

import { IconProperty } from '../../Misc'

function SemaphoreTable(props) {
  const { semaphores, fetching, tenant } = props
  const columns = [
    {
      title: <IconProperty icon={<FingerprintIcon />} value="Name" />,
      dataLabel: 'Name',
    },
    {
      title: <IconProperty icon={<TachometerAltIcon />} value="Current" />,
      dataLabel: 'Current',
    },
    {
      title: <IconProperty icon={<ResourcesFullIcon />} value="Max" />,
      dataLabel: 'Max',
    },
    {
      title: <IconProperty icon={<TenantIcon />} value="Global" />,
      dataLabel: 'Global',
    },
  ]

  function createSemaphoreRow(semaphore) {

    return {
      cells: [
        {
          title: (
            <Link to={`${tenant.linkPrefix}/semaphore/${semaphore.name}`}>{semaphore.name}</Link>
          ),
        },
        {
          title: semaphore.holders.count,
        },
        {
          title: semaphore.max,
        },
        {
          title: semaphore.global ? (
            <Label
              style={{
                marginLeft: 'var(--pf-global--spacer--sm)',
                verticalAlign: '0.15em',
              }}
            >
              Global
            </Label>
          ) : ''
        },
      ]
    }
  }

  function createFetchingRow() {
    const rows = [
      {
        heightAuto: true,
        cells: [
          {
            props: { colSpan: 8 },
            title: (
              <center>
                <Spinner size="xl" />
              </center>
            ),
          },
        ],
      },
    ]
    return rows
  }

  const haveSemaphores = semaphores && semaphores.length > 0

  let rows = []
  if (fetching) {
    rows = createFetchingRow()
    columns[0].dataLabel = ''
  } else {
    if (haveSemaphores) {
      rows = semaphores.map((semaphore) => createSemaphoreRow(semaphore))
    }
  }

  return (
    <>
      <Table
        aria-label="Semaphore Table"
        variant={TableVariant.compact}
        cells={columns}
        rows={rows}
        className="zuul-table"
      >
        <TableHeader />
        <TableBody />
      </Table>

      {/* Show an empty state in case we don't have any semaphores but are also not
          fetching */}
      {!fetching && !haveSemaphores && (
        <EmptyState>
          <EmptyStateIcon icon={LockIcon} />
          <Title headingLevel="h1">No semaphores found</Title>
          <EmptyStateBody>
            Nothing to display.
          </EmptyStateBody>
        </EmptyState>
      )}
    </>
  )
}

SemaphoreTable.propTypes = {
  semaphores: PropTypes.array,
  fetching: PropTypes.bool.isRequired,
  tenant: PropTypes.object,
  user: PropTypes.object,
  dispatch: PropTypes.func,
}

export default connect((state) => ({
  tenant: state.tenant,
  user: state.user,
}))(SemaphoreTable)
