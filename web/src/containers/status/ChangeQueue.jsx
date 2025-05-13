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

import React from 'react'
import PropTypes from 'prop-types'

import {
  Badge,
  Card,
  CardTitle,
  CardBody,
  Panel,
  ProgressStep,
  ProgressStepper,
  Title,
  Tooltip,
} from '@patternfly/react-core'

import QueueItem from './QueueItem'
import { getQueueItemIconConfig } from './Misc'

// This function will create a "tree-like" data structure to visualize
// multiple branches in a single ChangeQueue.
// The data structure is basically a linked-list that contains
// additional branches for items that are no longer relevant for the
// main branch (e.g. merge conflicts in a dependent pipeline). The base
// for the data structure is the "items_behind" relation of queue items.
// As a result, each queue item will have a single item_behind in the
// the main branch, while all other items_behind are moved to different
// branches.
//
// In the example below the items A, B, D and F build the "main" branch,
// while the items C and E create new branches (e.g. due to merge
// conflicts). G is the item behind E, so it will also be part of the
// branch starting with E.
//
// A
// |
// B
// |-C
// D
// |-E
// | |
// F G
const createTree = (head) => {
  // Root of the tree/linked list
  let tree = null

  // Map for easier lookup of items by their id
  // NOTE: If filters are applied, this map contains only the items that
  // match the filter criteria. This can break the lookup of
  // items_behind, so we have to be aware of this.
  const itemsById = {}

  // First iteration: Create map for "lookup by id"
  head.forEach(item => {
    itemsById[item.id] = item
  })

  // Second iteration: Move each item to the correct position within
  // the tree
  head.forEach(node => {
    // node._next builds a linked-list to visualize the "main" branch
    // of the queue.
    node._next = null
    // Branches will contain all items_behind which are not part of
    // main branch.
    node._branches = []

    // Create the root of the tree
    if (tree === null) {
      tree = node
    }

    if (node.items_behind.length === 0) {
      // Basically a continue for the forEach loop
      return
    }

    // Copy the items_behind, so we pop() already assigned items without
    // affecting the original array.
    const items_behind = node.items_behind.slice()
    if (items_behind.length > 1) {
      // The last element in the list is the item_behind on the "main"
      // branch
      const item_behind = itemsById[items_behind.pop()]
      // If filters are applied, the item_behind might have been removed
      // from the head and we won't be able to visualize it.
      if (item_behind) {
        node._next = item_behind
      }
      // All other items_behind are failing ones, so they should be
      // added to separate branches
      items_behind.forEach(item => {
        const item_behind = itemsById[item]
        // If filters are applied, the item_behind might have been
        // removed from the head and we won't be able to visualize it.
        if (item_behind) {
          node._branches.push(item_behind)
        }
      })
    } else {
      // We have only one element, so add it to the main branch
      const item_behind = itemsById[items_behind.pop()]
      // If filters are applied, the item_behind might have been removed
      // from the head and we won't be able to visualize it.
      if (item_behind) {
        node._next = item_behind
      }
    }
  })

  return tree
}

function BranchIcon({ item }) {
  const iconConfig = getQueueItemIconConfig(item)
  const Icon = iconConfig.icon

  let reason = 'Succeeding'

  if (item.active !== true) {
    reason = 'Waiting until closer to head of queue to start jobs'
  } else if (item.live !== true) {
    reason = 'Dependent item required for testing'
  } else if (item.failing_reasons && item.failing_reasons.length > 0) {
    reason = 'Failing because ' + item.failing_reasons.join(', ')
  }

  return (
    <Tooltip content={reason} position="bottom">
      <Icon color={iconConfig.color}/>
    </Tooltip>
  )
}

BranchIcon.propTypes = {
  item: PropTypes.object.isRequired,
}

// Recursively render QueueItems to visualize a ChangeQueue.
const Branch = ({ item, pipeline, jobsExpanded, newBranch = false }) => {
  const iconConfig = getQueueItemIconConfig(item)

  const step = (
    <>
      <ProgressStep
        variant={iconConfig.variant}
        id={item.id}
        titleId={item.id}
        icon={<BranchIcon item={item} />}
        style={{ marginBottom: '16px' }}
        key={`ps-${item.id}`}
      >
        <QueueItem item={item} pipeline={pipeline} jobsExpanded={jobsExpanded} />
        {/* To visualize a new branch, we put a ProgressStepper within
            the current ProgressStep. */}
        {item._branches.map((branch, idx) => (
          <Branch item={branch} pipeline={pipeline} newBranch={true} key={`br-${item.id}-${idx}`} jobsExpanded={jobsExpanded} />
        ))}
      </ProgressStep>
      {/* Items in the same branch must come after the current
          ProgressStep. We don't want them to be nested. */}
      {item._next !== null ? <Branch item={item._next} pipeline={pipeline} jobsExpanded={jobsExpanded} /> : ''}
    </>
  )

  const wrappedStep = (
    <div className="zuul-branch-wrapper">
      <ProgressStepper isVertical className="zuul-queue-branch">
        {step}
      </ProgressStepper>
    </div>
  )

  // If we want to start a new branch, we have to wrap the current
  // branch into a new ProgressStepper.
  if (newBranch) {
    return wrappedStep
  }

  // Otherwise, just return the current step
  return step
}

Branch.propTypes = {
  item: PropTypes.object.isRequired,
  pipeline: PropTypes.object.isRequired,
  newBranch: PropTypes.bool,
  jobsExpanded: PropTypes.bool,
}

function ChangeQueue({ queue, pipeline, jobsExpanded, showTitle=true }) {
  // TODO (felix): Use useMemo hook to cache the rendered tree across re-renders
  const trees = []
  queue.heads.filter(head => head.length > 0).forEach(head => (
    trees.push(createTree(head))
  ))

  return (
    <>
      <Card isPlain className="zuul-change-queue zuul-compact-card">
        {showTitle && queue.name ?
          <CardTitle className="zuul-change-queue-name">
            <Title headingLevel="h3" style={{ padding: 0, margin: 0 }}>
              {queue.name}
              {queue.branch ? ` (${queue.branch})` : ''}
              <Tooltip
                content={
                  <div style={{ textAlign: 'left' }}>
                    Queue length: {queue._count}<br />Window size: {queue.window}
                  </div>
                }
              >
                <Badge
                  isRead
                  style={{ marginLeft: 'var(--pf-global--spacer--sm)', verticalAlign: '0.1em' }}
                >
                  {queue._count} / {queue.window}
                </Badge>
              </Tooltip>
            </Title>
          </CardTitle>
          : ''}
        <CardBody className="zuul-change-queue-body">
          <Panel>
            {trees.map(tree => (
              <ProgressStepper key={tree.id} isVertical>
                <Branch item={tree} pipeline={pipeline} jobsExpanded={jobsExpanded} />
              </ProgressStepper>
            ))}
          </Panel>
        </CardBody>
      </Card>
    </>
  )
}

ChangeQueue.propTypes = {
  queue: PropTypes.object,
  pipeline: PropTypes.object,
  tenant: PropTypes.object,
  showTitle: PropTypes.bool,
  jobsExpanded: PropTypes.bool,
}

export default ChangeQueue
