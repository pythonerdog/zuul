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
import { connect } from 'react-redux'
import PropTypes from 'prop-types'
import { Link } from 'react-router-dom'
import {
  BuildIcon,
  CubeIcon,
  DesktopIcon,
  FolderIcon,
  HomeIcon,
  RepositoryIcon,
  ThumbtackIcon,
} from '@patternfly/react-icons'
import {
  Table,
  TableHeader,
  TableBody,
  TableVariant,
} from '@patternfly/react-table'
import { Fetching } from '../containers/Fetching'
import { fetchTenantsIfNeeded } from '../actions/tenants'
import { PageSection, PageSectionVariants } from '@patternfly/react-core'
import { IconProperty } from '../Misc'

class TenantsPage extends React.Component {
  static propTypes = {
    remoteData: PropTypes.object,
    dispatch: PropTypes.func
  }

  updateData = (force) => {
    this.props.dispatch(fetchTenantsIfNeeded(force))
  }

  componentDidMount() {
    document.title = 'Zuul Tenants'
    this.updateData()
  }

  // TODO: fix Refreshable class to work with tenant less page.
  componentDidUpdate() { }

  render() {
    const { remoteData } = this.props
    if (remoteData.isFetching) {
      return <Fetching />
    }

    const tenants = remoteData.tenants.map((tenant) => {
      return {
        cells: [
          { title: (<b>{tenant.name}</b>) },
          { title: (<Link to={'/t/' + tenant.name + '/status'}>Status</Link>) },
          { title: (<Link to={'/t/' + tenant.name + '/projects'}>Projects</Link>) },
          { title: (<Link to={'/t/' + tenant.name + '/jobs'}>Jobs</Link>) },
          { title: (<Link to={'/t/' + tenant.name + '/builds'}>Builds</Link>) },
          { title: (<Link to={'/t/' + tenant.name + '/buildsets'}>Buildsets</Link>) },
          { title: (<Link to={'/t/' + tenant.name + '/autoholds'}>Autoholds</Link>) },
        ]
      }
    })
    const columns = [
      {
        title: <IconProperty icon={<HomeIcon />} value="Name" />,
        dataLabel: 'Name',
      },
      {
        title: <IconProperty icon={<DesktopIcon />} value="Status" />,
        dataLabel: 'Status',
      },
      {
        title: <IconProperty icon={<CubeIcon />} value="Projects" />,
        dataLabel: 'Projects',
      },
      {
        title: <IconProperty icon={<BuildIcon />} value="Jobs" />,
        dataLabel: 'Jobs',
      },
      {
        title: <IconProperty icon={<FolderIcon />} value="Builds" />,
        dataLabel: 'Builds',
      },
      {
        title: <IconProperty icon={<RepositoryIcon />} value="Buildsets" />,
        dataLabel: 'Buildsets',
      },
      {
        title: <IconProperty icon={<ThumbtackIcon />} value="Autoholds" />,
        dataLabel: 'Autoholds',
      },
    ]

    return (
      <PageSection variant={PageSectionVariants.light}>
        <Table
          aria-label="Tenant Table"
          variant={TableVariant.compact}
          cells={columns}
          rows={tenants}
          className="zuul-tenant-table"
        >
          <TableHeader />
          <TableBody />
        </Table>
      </PageSection>
    )
  }
}

export default connect(state => ({ remoteData: state.tenants }))(TenantsPage)
