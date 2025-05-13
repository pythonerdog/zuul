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
import { Link } from 'react-router-dom'
import { PageSection, PageSectionVariants } from '@patternfly/react-core'
import {
  Table,
  TableVariant,
  TableHeader,
  TableBody,
} from '@patternfly/react-table'
import {
  CubeIcon,
  ConnectedIcon,
} from '@patternfly/react-icons'
import { IconProperty } from '../Misc'

import { fetchProjectsIfNeeded } from '../actions/projects'
import { Fetchable, Fetching } from '../containers/Fetching'


class ProjectsPage extends React.Component {
  static propTypes = {
    tenant: PropTypes.object,
    remoteData: PropTypes.object,
    dispatch: PropTypes.func
  }

  updateData = (force) => {
    this.props.dispatch(fetchProjectsIfNeeded(this.props.tenant, force))
  }

  componentDidMount () {
    document.title = 'Zuul Projects'
    if (this.props.tenant.name) {
      this.updateData()
    }
  }

  componentDidUpdate (prevProps) {
    if (this.props.tenant.name !== prevProps.tenant.name) {
      this.updateData()
    }
  }

  render () {
    const { remoteData } = this.props
    const projects = remoteData.projects[this.props.tenant.name]

    // TODO (felix): Can we somehow differentiate between "no projects yet" (due
    // to fetching) and "no projects at all", so we could show an empty state
    // in the latter case. The same applies for other pages like labels, nodes,
    // buildsets, ... as well.
    if (!projects) {
      return <Fetching />
    }

    const columns = [
      {
        title: <IconProperty icon={<CubeIcon />} value="Name" />,
        dataLabel: 'name',
      },
      {
        title: <IconProperty icon={<ConnectedIcon />} value="Connection" />,
        dataLabel: 'connection',
      },
      {
        title: 'Type',
        dataLabel: 'type',
      },
      {
        title: 'Last builds',
        dataLabel: 'last-builds',
      }
    ]
    let rows = []
    projects.forEach((project) => {
      let r = {
        cells: [
          {title: <Link to={this.props.tenant.linkPrefix + '/project/' + project.canonical_name}>{project.name}</Link>, props: {column: 'Name'}},
          {title: project.connection_name, props: {column: 'Connection'}},
          {title: project.type, props: {column: 'Type'}},
          {title: <Link to={this.props.tenant.linkPrefix + '/builds?project=' + project.name}>Builds</Link>, props: {column: 'Last builds'}},
        ]
      }
      rows.push(r)
    })
    return (
      <PageSection variant={PageSectionVariants.light}>
        <PageSection style={{paddingRight: '5px'}}>
          <Fetchable
            isFetching={remoteData.isFetching}
            fetchCallback={this.updateData}
          />
        </PageSection>
        <Table
          aria-label="Projects Table"
          variant={TableVariant.compact}
          cells={columns}
          rows={rows}
          className="zuul-table"
        >
          <TableHeader />
          <TableBody />
        </Table>
      </PageSection>
    )
  }
}

export default connect(state => ({
  tenant: state.tenant,
  remoteData: state.projects,
}))(ProjectsPage)
