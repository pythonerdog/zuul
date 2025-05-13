// Copyright 2020 BMW Group
// Copyright 2023 Acme Gating, LLC
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
  Button,
  EmptyState,
  EmptyStateBody,
  EmptyStateIcon,
  EmptyStateSecondaryActions,
  Spinner,
  Title,
  DropdownToggle,
} from '@patternfly/react-core'
import {
  InfoCircleIcon,
  CodeBranchIcon,
  CodeIcon,
  CubeIcon,
  StreamIcon,
  FlagIcon,
  FilterIcon,
} from '@patternfly/react-icons'
import {
  Table,
  TableHeader,
  TableBody,
  TableVariant,
  truncate,
  breakWord,
  cellWidth,
  expandable,
} from '@patternfly/react-table'

import { IconProperty } from '../../Misc'

function ConfigErrorTable({
  errors,
  fetching,
  onClearFilters,
  preferences,
  addFilter,
}) {

  const [expandedRows, setExpandedRows] = React.useState([])
  const setRowExpanded = (idx, isExpanding = true) =>
        setExpandedRows(prevExpanded => {
          const otherExpandedRows = prevExpanded.filter(r => r !== idx)
          return isExpanding ?
                [...otherExpandedRows, idx] : otherExpandedRows
        })
  const isRowExpanded = idx => expandedRows.includes(idx)

  let zuulOutputClass = 'zuul-build-output'
  if (preferences.darkMode) {
    zuulOutputClass = 'zuul-build-output-dark'
  }

  const columns = [
    {
      title: <IconProperty icon={<CubeIcon />} value="Project" />,
      dataLabel: 'Project',
      cellTransforms: [breakWord],
      cellFormatters: [expandable],
    },
    {
      title: <IconProperty icon={<CodeBranchIcon />} value="Branch" />,
      dataLabel: 'Branch',
      cellTransforms: [breakWord],
    },
    {
      title: <IconProperty icon={<StreamIcon />} value="Severity" />,
      dataLabel: 'Severity',
    },
    {
      title: <IconProperty icon={<CodeIcon />} value="Name" />,
      dataLabel: 'Name',
    },
    {
      title: <IconProperty icon={<FlagIcon />} value="Message" />,
      dataLabel: 'Message',
      transforms: [cellWidth(20)],
      cellTransforms: [truncate],
    },
  ]

  function createConfigErrorRow(rows, error) {
    return {
      id: rows.length,
      isOpen: isRowExpanded(rows.length),
      cells: [
        {
          title: error.source_context.project,
          filterCategory: 'project'
        },
        {
          title: error.source_context.branch,
          filterCategory: 'branch'
        },
        {
          title: error.severity,
          filterCategory: 'severity'
        },
        {
          title: error.name,
          filterCategory: 'name'
        },
        {
          title: error.short_error,
        },
      ],
    }
  }

  function createConfigErrorDetailRow(rows, error) {
    return {
      id: rows.length,
      parent: rows.length - 1,
      cells: [
        {
          title: <pre className={zuulOutputClass}>{error.error}</pre>,
        },
      ],
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

  let rows = []
  if (fetching) {
    rows = createFetchingRow()
    // The dataLabel property is used to show the column header in a list-like
    // format for smaller viewports. When we are fetching, we don't want the
    // fetching row to be prepended by a "Job" column header. The other column
    // headers are not relevant here since we only have a single cell in the
    // fetcihng row.
    columns[0].dataLabel = ''
  } else {
    rows = []
    errors.forEach(error => {
      rows.push(createConfigErrorRow(rows, error))
      rows.push(createConfigErrorDetailRow(rows, error))
    })
  }

  const actionResolver = (rowData) => {
    if (rowData.parent !== undefined) {
      return []
    }
    const cells = rowData.cells.filter(cell =>
      cell.filterCategory
    )
    return cells.map(cell => {
      return {
        title: `Filter by ${cell.filterCategory}: ${cell.title} `,
        onClick: () => {addFilter(cell.filterCategory, cell.title)}
      }
    })
  }

  const filterToggle = (filterProps) => (
    <DropdownToggle toggleIndicator={null} onToggle={filterProps.onToggle}>
      <FilterIcon color='var(--pf-global--Color--200)'/>
    </DropdownToggle>
  )

  return (
    <>
      <Table
        aria-label="Config Errors Table"
        variant={TableVariant.compact}
        cells={columns}
        rows={rows}
        actionResolver={actionResolver}
        onCollapse={(_event, rowIndex, isOpen) => {
          setRowExpanded(rowIndex, isOpen)
        }}
        actionsToggle={filterToggle}
      >
        <TableHeader />
        <TableBody />
      </Table>

      {/* Show an empty state in case we don't have any errors but are also not
          fetching */}
      {!fetching && errors.length === 0 && (
        <EmptyState>
          <EmptyStateIcon icon={InfoCircleIcon} />
          <Title headingLevel="h1">No errors found</Title>
          <EmptyStateBody>
            No errors match this filter criteria. Remove some filters or clear
            all to show results.
          </EmptyStateBody>
          <EmptyStateSecondaryActions>
            <Button variant="link" onClick={onClearFilters}>
              Clear all filters
            </Button>
          </EmptyStateSecondaryActions>
        </EmptyState>
      )}
    </>
  )
}

ConfigErrorTable.propTypes = {
  errors: PropTypes.array.isRequired,
  fetching: PropTypes.bool.isRequired,
  onClearFilters: PropTypes.func.isRequired,
  preferences: PropTypes.object.isRequired,
  addFilter: PropTypes.func.isRequired,
}

export default connect((state) => ({
  preferences: state.preferences,
}))(ConfigErrorTable)
