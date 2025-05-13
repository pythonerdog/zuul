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

function LabelTable(props) {
  const { labels, fetching } = props
  const columns = [
    {
      title: 'Name',
      dataLabel: 'Name',
    },
  ]

  function createLabelRow(label) {
    return {
      cells: [
        {
          title: label.name,
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

  const haveLabels = labels && labels.length > 0

  let rows = []
  if (fetching) {
    rows = createFetchingRow()
    columns[0].dataLabel = ''
  } else {
    if (haveLabels) {
      rows = labels.map((label) => createLabelRow(label))
    }
  }

  return (
    <>
      <Table
        aria-label="Label Table"
        variant={TableVariant.compact}
        cells={columns}
        rows={rows}
        className="zuul-table"
      >
        <TableHeader />
        <TableBody />
      </Table>

      {/* Show an empty state in case we don't have any labels but are also not
          fetching */}
      {!fetching && !haveLabels && (
        <EmptyState>
          <Title headingLevel="h1">No labels found</Title>
          <EmptyStateBody>
            Nothing to display.
          </EmptyStateBody>
        </EmptyState>
      )}
    </>
  )
}

LabelTable.propTypes = {
  labels: PropTypes.array,
  fetching: PropTypes.bool.isRequired,
}

export default LabelTable
