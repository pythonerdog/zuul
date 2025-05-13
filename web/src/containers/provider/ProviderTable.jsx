// Copyright 2020 Red Hat, Inc
// Copyright 2022, 2024 Acme Gating, LLC
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
  Spinner,
  Title,
} from '@patternfly/react-core'
import {
  Table,
  TableHeader,
  TableBody,
  TableVariant,
} from '@patternfly/react-table'
import { Link } from 'react-router-dom'

function ProviderTable(props) {
  const { providers, fetching, tenant } = props
  const columns = [
    {
      title: 'Name',
      dataLabel: 'Name',
    },
  ]

  function createProviderRow(provider) {
    return {
      cells: [
        {
          title: (
            <Link to={`${tenant.linkPrefix}/provider/${provider.name}`}>{provider.name}</Link>
          ),
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

  const haveProviders = providers && providers.length > 0

  let rows = []
  if (fetching) {
    rows = createFetchingRow()
    columns[0].dataLabel = ''
  } else {
    if (haveProviders) {
      rows = providers.map((provider) => createProviderRow(provider))
    }
  }

  return (
    <>
      <Table
        aria-label="Provider Table"
        variant={TableVariant.compact}
        cells={columns}
        rows={rows}
        className="zuul-table"
      >
        <TableHeader />
        <TableBody />
      </Table>

      {/* Show an empty state in case we don't have any providers but are also not
          fetching */}
      {!fetching && !haveProviders && (
        <EmptyState>
          <Title headingLevel="h1">No providers found</Title>
          <EmptyStateBody>
            Nothing to display.
          </EmptyStateBody>
        </EmptyState>
      )}
    </>
  )
}

ProviderTable.propTypes = {
  providers: PropTypes.array,
  fetching: PropTypes.bool.isRequired,
  tenant: PropTypes.object,
  user: PropTypes.object,
  dispatch: PropTypes.func,
}

export default connect((state) => ({
  tenant: state.tenant,
  user: state.user,
}))(ProviderTable)
