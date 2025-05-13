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
import {
  List,
  ListItem,
  TreeView
} from '@patternfly/react-core'

import {
  ServerIcon,
  TagIcon
} from '@patternfly/react-icons'

class Nodeset extends React.Component {
  static propTypes = {
    nodeset: PropTypes.object.isRequired
  }

  constructor(props) {
    super(props)

    this.state = { activeItems: {} }

    // eslint-disable-next-line no-unused-vars
    this.onSelect = (event, treeViewItem) => {
      this.setState({
        /* NOTE(ianw) 2021-08-13 : override this
         * from standard [treeViewItem] as we don't want
         * anything selectable.
         */
        activeItems: {}
      })
    }
  }

  render () {
    const { nodeset } = this.props

    const { activeItems } = this.state

    const nodes = []
    nodeset.nodes.forEach((node) => {
      nodes.push(
        {
          name: (
            <List isPlain>
              <ListItem icon={<TagIcon />}>{node.name}</ListItem>
              <ListItem icon={<ServerIcon />}>{node.label}</ListItem>
            </List>),
          id: node.name + node.label,
        }
      )
    })
    const groups = []
    nodeset.groups.forEach((group) => {
      let group_children = []
      group.nodes.forEach((child_node) => {
        group_children.push(
          {
            name: (
              <List isPlain>
                <ListItem icon={<TagIcon />}>{child_node}</ListItem>
              </List>
            ),
            id: child_node
          }
        )})
      groups.push(
        {
          name: group.name,
          id: group.name,
          children: group_children
        }
      )
    })
    const options = [
      {
        name: 'Nodeset ' + nodeset.name,
        id: 'nodes',
        children: nodes
      },
      {
        name: 'Node Groups',
        id: 'groups',
        children: groups
      }
    ]

    return (
      <React.Fragment>
        <TreeView data={options} activeItems={activeItems} onSelect={this.onSelect} />
      </React.Fragment>
    )
  }
}

export default Nodeset
