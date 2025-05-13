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
import {
  Table,
  TableVariant,
  TableHeader,
  TableBody,
} from '@patternfly/react-table'
import * as moment from 'moment'
import {
  PageSection,
  PageSectionVariants,
  ClipboardCopy,
} from '@patternfly/react-core'
import {
  BuildIcon,
  ClusterIcon,
  ConnectedIcon,
  OutlinedCalendarAltIcon,
  TagIcon,
  RunningIcon,
  PencilAltIcon,
  ZoneIcon,
} from '@patternfly/react-icons'
import { IconProperty } from '../Misc'

import { fetchNodesIfNeeded } from '../actions/nodes'
import { Fetchable } from '../containers/Fetching'


class NodesPage extends React.Component {
  static propTypes = {
    tenant: PropTypes.object,
    remoteData: PropTypes.object,
    dispatch: PropTypes.func
  }

  updateData = (force) => {
    this.props.dispatch(fetchNodesIfNeeded(this.props.tenant, force))
  }

  componentDidMount () {
    document.title = 'Zuul Nodes'
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
    const nodes = remoteData.nodes

    const columns = [
      {
        title: (
          <IconProperty icon={<BuildIcon />} value="ID" />
        ),
        dataLabel: 'id',
      },
      {
        title: (
          <IconProperty icon={<TagIcon />} value="Labels" />
        ),
        dataLabel: 'labels',
      },
      {
        title: (
          <IconProperty icon={<ConnectedIcon />} value="Connection" />
        ),
        dataLabel: 'connection',
      },
      {
        title: (
          <IconProperty icon={<ClusterIcon />} value="Server" />
        ),
        dataLabel: 'server',
      },
      {
        title: (
          <IconProperty icon={<ZoneIcon />} value="Provider" />
        ),
        dataLabel: 'provider',
      },
      {
        title: (
          <IconProperty icon={<RunningIcon />} value="State" />
        ),
        dataLabel: 'state',
      },
      {
        title: (
          <IconProperty icon={<OutlinedCalendarAltIcon />} value="Age" />
        ),
        dataLabel: 'age',
      },
      {
        title: (
          <IconProperty icon={<PencilAltIcon />} value="Comment" />
        ),
        dataLabel: 'comment',
      }
    ]
    let rows = []
    nodes.forEach((node) => {
        const extid = typeof(node.external_id) === 'string'?
              node.external_id : JSON.stringify(node.external_id)
        let r = [
            {title: node.id, props: {column: 'ID'}},
            {title: node.type.join(','), props: {column: 'Label' }},
            {title: node.connection_type, props: {column: 'Connection'}},
            {title: <ClipboardCopy hoverTip="Copy" clickTip="Copied" variant="inline-compact">{extid}</ClipboardCopy>, props: {column: 'Server'}},
            {title: node.provider, props: {column: 'Provider'}},
            {title: node.state, props: {column: 'State'}},
            {title: moment.unix(node.state_time).fromNow(), props: {column: 'Age'}},
            {title: node.comment, props: {column: 'Comment'}},
        ]
        rows.push({cells: r})
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
          aria-label="Nodes Table"
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
  remoteData: state.nodes,
}))(NodesPage)
