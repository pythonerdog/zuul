// Copyright 2021 Red Hat
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
import {
  DataList,
  DataListCell,
  DataListItem,
  DataListItemRow,
  DataListItemCells,
} from '@patternfly/react-core'

class HeldBuildList extends React.Component {
  static propTypes = {
    nodes: PropTypes.array,
    tenant: PropTypes.object,
  }

  constructor() {
    super()
    this.state = {
      selectedBuildId: null,
    }
  }

  handleSelectDataListItem = (buildId) => {
    this.setState({
      selectedBuildId: buildId,
    })
  }

  /* TODO find a way to add some more useful info than just the build's UUID,
     like a timestamp and a change number */
  render() {
    const { nodes, tenant } = this.props
    const { selectedBuildId } = this.state
    return (
      <DataList
        className="zuul-build-list"
        isCompact
        selectedDataListItemId={selectedBuildId}
        onSelectDataListItem={this.handleSelectDataListItem}
        style={{ fontSize: 'var(--pf-global--FontSize--md)' }}
      >
        {nodes.map((node) => (
          <DataListItem key={node.build} id={node.build}>
            <Link
              to={`${tenant.linkPrefix}/build/${node.build}`}
              style={{
                textDecoration: 'none',
              }}
            >
              <DataListItemRow>
                <DataListItemCells
                  dataListCells={[
                    <DataListCell key={node.build} width={3}>
                      {node.build}
                    </DataListCell>,
                  ]}
                />
              </DataListItemRow>
            </Link>
          </DataListItem>
        ))}
      </DataList>
    )
  }
}

export default connect((state) => ({ tenant: state.tenant }))(HeldBuildList)
