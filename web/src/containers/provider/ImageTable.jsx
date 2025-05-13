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
import { Link } from 'react-router-dom'

function ImageTable(props) {
  const { images, fetching, linkPrefix } = props
  const columns = [
    {
      title: 'Name',
      dataLabel: 'Name',
    },
  ]

  function createImageRow(image) {
    return {
      cells: [
        {
          title: (
            <Link to={`${linkPrefix}/${image.name}`}>{image.name}</Link>
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

  const haveImages = images && images.length > 0

  let rows = []
  if (fetching) {
    rows = createFetchingRow()
    columns[0].dataLabel = ''
  } else {
    if (haveImages) {
      rows = images.map((image) => createImageRow(image))
    }
  }

  return (
    <>
      <Table
        aria-label="Image Table"
        variant={TableVariant.compact}
        cells={columns}
        rows={rows}
        className="zuul-table"
      >
        <TableHeader />
        <TableBody />
      </Table>

      {/* Show an empty state in case we don't have any images but are also not
          fetching */}
      {!fetching && !haveImages && (
        <EmptyState>
          <Title headingLevel="h1">No images found</Title>
          <EmptyStateBody>
            Nothing to display.
          </EmptyStateBody>
        </EmptyState>
      )}
    </>
  )
}

ImageTable.propTypes = {
  images: PropTypes.array,
  fetching: PropTypes.bool.isRequired,
  linkPrefix: PropTypes.string,
}

export default ImageTable
