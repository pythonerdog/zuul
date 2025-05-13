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

import React, { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { capitalize } from '@patternfly/react-core'
import {
  expandable,
  Table,
  TableBody,
  TableHeader,
  TableVariant,
} from '@patternfly/react-table'
import {
  CodeIcon,
  OnRunningIcon,
  OutlinedHddIcon,
  PauseCircleIcon,
  RunningIcon,
  QuestionIcon,
  StopCircleIcon,
  HistoryIcon,
} from '@patternfly/react-icons'

import { IconProperty } from '../../Misc'

const STATE_ICON_CONFIGS = {
  RUNNING: {
    icon: RunningIcon,
    color: 'var(--pf-global--success-color--100)',
  },
  INITIALIZING: {
    icon: HistoryIcon,
    color: 'var(--pf-global--warning-color--100)',
  },
  PAUSED: {
    icon: PauseCircleIcon,
    color: 'var(--pf-global--warning-color--100)',
  },
  STOPPED: {
    icon: StopCircleIcon,
    color: 'var(--pf-global--danger-color--100)',
  },
}

const DEFAULT_STATE_ICON_CONFIG = {
  icon: QuestionIcon,
  color: 'var(--pf-global--info-color--100)',
}

function ComponentStateIcon({ state }) {
  const iconConfig =
    STATE_ICON_CONFIGS[state.toUpperCase()] || DEFAULT_STATE_ICON_CONFIG
  const Icon = iconConfig.icon

  return (
    <span style={{ color: iconConfig.color }}>
      <Icon
        size="sm"
        style={{
          marginRight: 'var(--pf-global--spacer--sm)',
          verticalAlign: '-0.2em',
        }}
      />
    </span>
  )
}

ComponentStateIcon.propTypes = {
  state: PropTypes.string.isRequired,
}

function ComponentState({ state }) {
  const iconConfig =
    STATE_ICON_CONFIGS[state.toUpperCase()] || DEFAULT_STATE_ICON_CONFIG

  return <span style={{ color: iconConfig.color }}>{state.toUpperCase()}</span>
}

ComponentState.propTypes = {
  state: PropTypes.string.isRequired,
}

function ComponentTable({ components }) {
  // We have to keep the rows in state to be complient to how the PF4
  // expandable/collapsible table works (see the handleCollapse function).
  const [rows, setRows] = useState([])

  const sortComponents = (a, b) => {
    if (a.hostname < b.hostname) {
      return -1
    }
    if (a.hostname > b.hostname) {
      return 1
    }
    return 0
  }

  useEffect(() => {
    const createTableRows = () => {
      const allRows = []
      let i = 0
      let sectionIndex = 0
      for (const [kind, _components] of Object.entries(components)) {
        sectionIndex = i
        i++
        const sectionRows = []
        for (const component of [..._components].sort(sortComponents)) {
          sectionRows.push(createComponentRow(kind, component, sectionIndex))
          i++
        }
        allRows.push(createSectionRow(kind, sectionRows.length))
        allRows.push(...sectionRows)
      }

      return allRows
    }

    setRows(createTableRows())
    // Ensure that the effect is only called once and not after each
    // render (which would happen if no dependency array is provided).
    // But as we are changing the state during the effect, this would
    // result in an infinite render loop as every state change
    // re-renders the component.
    // Side note: We could also pass an empty depdency array here, but
    // eslint is complaining about that. So we provide the components
    // variable which is provided via props and thus doesn't change
    // during the lifetime of this react component.
  }, [components])

  // TODO (felix): We could change this to an expandable table and show some
  // details about the component in the expandable row. E.g. similar to what
  // OpenShift shows in for deployments and pods (metrics, performance,
  // additional attributes).
  const columns = [
    {
      title: <IconProperty icon={<OutlinedHddIcon />} value="Hostname" />,
      dataLabel: 'Hostname',
      cellFormaters: [expandable],
    },
    {
      title: <IconProperty icon={<OnRunningIcon />} value="State" />,
      dataLabel: 'State',
    },
    {
      title: <IconProperty icon={<CodeIcon />} value="Version" />,
      dataLabel: 'Version',
    },
  ]

  function createSectionRow(kind, childrenCount) {
    return {
      // Keep all sections open on initial page load. The handleCollapse()
      // function will deal with open/closing sections.
      isOpen: true,
      cells: [`${capitalize(kind)} (${childrenCount})`],
    }
  }

  function createComponentRow(kind, component, parent_id) {
    return {
      parent: parent_id,
      cells: [
        {
          title: (
            <>
              <ComponentStateIcon state={component.state} />{' '}
              {component.hostname}
            </>
          ),
        },
        {
          title: <ComponentState state={component.state} />,
        },
        component.version,
      ],
    }
  }

  function handleCollapse(event, rowKey, isOpen) {
    const _rows = [...rows]
    /* Note from PF4:
     * Please do not use rowKey as row index for more complex tables.
     * Rather use some kind of identifier like ID passed with each row.
     */
    rows[rowKey].isOpen = isOpen
    setRows(_rows)
  }

  return (
    /* NOTE (felix): The mobile version of this expandable table looks kind of
     * broken, but the same applies to the example in the PF4 documentation:
     * https://www.patternfly.org/2020.04/documentation/react/components/table#compact-expandable
     *
     * I don't think this is something we have to attract now, but we should
     * keep this note as reference.
     */
    <>
      <Table
        aria-label="Components Table"
        variant={TableVariant.compact}
        onCollapse={handleCollapse}
        cells={columns}
        rows={rows}
        className="zuul-build-table"
      >
        <TableHeader />
        <TableBody />
      </Table>
    </>
  )
}

ComponentTable.propTypes = {
  components: PropTypes.object.isRequired,
}

export default ComponentTable
