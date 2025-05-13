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

import {
  Button,
  Dropdown,
  DropdownItem,
  KebabToggle,
  Modal,
  ModalVariant
} from '@patternfly/react-core'
import {
  AngleDoubleUpIcon,
  BanIcon,
} from '@patternfly/react-icons'
import { dequeue, dequeue_ref, promote } from '../../api'
import { addDequeueError, addPromoteError } from '../../actions/adminActions'

import { addNotification } from '../../actions/notifications'
import { fetchStatusIfNeeded } from '../../actions/status'

import LineAngleImage from '../../images/line-angle.png'
import LineTImage from '../../images/line-t.png'
import LineAngleDarkImage from '../../images/line-angle-dark.png'
import LineTDarkImage from '../../images/line-t-dark.png'
import ItemPanel from './ItemPanel'

function getRef(item) {
  // For backwards compat: get a representative ref for this item
  // if there is more than one.
  return 'refs' in item ? item.refs[0] : item
}

class Item extends React.Component {
  static propTypes = {
    item: PropTypes.object.isRequired,
    queue: PropTypes.object.isRequired,
    expanded: PropTypes.bool.isRequired,
    pipeline: PropTypes.object,
    tenant: PropTypes.object,
    user: PropTypes.object,
    dispatch: PropTypes.func,
    preferences: PropTypes.object
  }

  state = {
    showDequeueModal: false,
    showPromoteModal: false,
    showAdminActions: false,
  }

  dequeueConfirm = () => {
    const { tenant, item, pipeline } = this.props
    const ref = getRef(item)
    // Use the first ref as a proxy for the item since queue
    // commands operate on changes
    let projectName = ref.project
    let refId = ref.id || 'N/A'
    let refRef = ref.ref
    this.setState(() => ({ showDequeueModal: false }))
    if (/^[0-9a-f]{40}$/.test(refId)) {
      // post-merge with a ref update (tag, branch push)
      dequeue_ref(tenant.apiPrefix, projectName, pipeline.name, refRef)
        .then(() => {
          this.props.dispatch(fetchStatusIfNeeded(tenant))
        })
        .catch(error => {
          this.props.dispatch(addDequeueError(error))
        })
    } else if (refId !== 'N/A') {
      // pre-merge, ie we have a change id
      dequeue(tenant.apiPrefix, projectName, pipeline.name, refId)
        .then(() => {
          this.props.dispatch(fetchStatusIfNeeded(tenant))
        })
        .catch(error => {
          this.props.dispatch(addDequeueError(error))
        })
    } else {
      // periodic with only a ref (branch head)
      dequeue_ref(tenant.apiPrefix, projectName, pipeline.name, refRef)
        .then(() => {
          this.props.dispatch(fetchStatusIfNeeded(tenant))
        })
        .catch(error => {
          this.props.dispatch(addDequeueError(error))
        })
    }
  }

  dequeueCancel = () => {
    this.setState(() => ({ showDequeueModal: false }))
  }

  renderDequeueModal() {
    const { showDequeueModal } = this.state
    const { item } = this.props
    const ref = getRef(item)
    let projectName = ref.project
    let refId = ref.id || ref.ref
    const title = 'You are about to dequeue a change'
    return (
      <Modal
        variant={ModalVariant.small}
        // titleIconVariant={BullhornIcon}
        isOpen={showDequeueModal}
        title={title}
        onClose={this.dequeueCancel}
        actions={[
          <Button key="deq_confirm" variant="primary" onClick={this.dequeueConfirm}>Confirm</Button>,
          <Button key="deq_cancel" variant="link" onClick={this.dequeueCancel}>Cancel</Button>,
        ]}>
        <p>Please confirm that you want to cancel <strong>all ongoing builds</strong> on change <strong>{refId}</strong> for project <strong>{projectName}</strong>.</p>
      </Modal>
    )
  }

  promoteConfirm = () => {
    const { tenant, item, pipeline } = this.props
    const ref = getRef(item)
    let refId = ref.id || 'NA'
    this.setState(() => ({ showPromoteModal: false }))
    if (refId !== 'N/A') {
      promote(tenant.apiPrefix, pipeline.name, [refId,])
        .then(() => {
          this.props.dispatch(fetchStatusIfNeeded(tenant))
        })
        .catch(error => {
          this.props.dispatch(addPromoteError(error))
        })
    } else {
      this.props.dispatch(addNotification({
        url: null,
        status: 'Invalid change ' + refId + ' for promotion',
        text: '',
        type: 'error'
      }))
    }
  }

  promoteCancel = () => {
    this.setState(() => ({ showPromoteModal: false }))
  }

  renderPromoteModal() {
    const { showPromoteModal } = this.state
    const { item } = this.props
    const ref = getRef(item)
    let refId = ref.id || 'N/A'
    const title = 'You are about to promote a change'
    return (
      <Modal
        variant={ModalVariant.small}
        // titleIconVariant={BullhornIcon}
        isOpen={showPromoteModal}
        title={title}
        onClose={this.promoteCancel}
        actions={[
          <Button key="prom_confirm" variant="primary" onClick={this.promoteConfirm}>Confirm</Button>,
          <Button key="prom_cancel" variant="link" onClick={this.promoteCancel}>Cancel</Button>,
        ]}>
        <p>Please confirm that you want to promote change <strong>{refId}</strong>.</p>
      </Modal>
    )
  }

  renderAdminCommands(idx) {
    const { showAdminActions } = this.state
    const { queue } = this.props
    const dropdownCommands = [
      <DropdownItem
        key="dequeue"
        icon={<BanIcon style={{
          color: 'var(--pf-global--danger-color--100)',
        }} />}
        description="Stop all jobs for this item"
        onClick={(event) => {
          event.preventDefault()
          this.setState(() => ({ showDequeueModal: true }))
        }}
      >Dequeue</DropdownItem>,
      <DropdownItem
        key="promote"
        icon={<AngleDoubleUpIcon style={{
          color: 'var(--pf-global--default-color--200)',
        }} />}
        description="Promote this item to the top of the queue"
        onClick={(event) => {
          event.preventDefault()
          this.setState(() => ({ showPromoteModal: true }))
        }}
      >Promote</DropdownItem>
    ]
    return (
      <Dropdown
        title='Actions'
        isOpen={showAdminActions}
        onSelect={() => {
          this.setState({ showAdminActions: !showAdminActions })
          const element = document.getElementById('toggle-id-' + idx + '-' + queue.uuid)
          element.focus()
        }}
        dropdownItems={dropdownCommands}
        isPlain
        toggle={
          <KebabToggle
            onToggle={(showAdminActions) => {
              this.setState({ showAdminActions })
            }}
            id={'toggle-id-' + idx + '-' + queue.uuid} />
        }
      />
    )

  }

  renderStatusIcon(item) {
    let iconGlyph = 'pficon pficon-ok'
    let iconTitle = 'Succeeding'
    if (item.active !== true) {
      iconGlyph = 'pficon pficon-pending'
      iconTitle = 'Waiting until closer to head of queue to' +
        ' start jobs'
    } else if (item.live !== true) {
      iconGlyph = 'pficon pficon-info'
      iconTitle = 'Dependent item required for testing'
    } else if (item.failing_reasons &&
      item.failing_reasons.length > 0) {
      let reason = item.failing_reasons.join(', ')
      iconTitle = 'Failing because ' + reason
      if (reason.match(/merge conflict/)) {
        iconGlyph = 'pficon pficon-error-circle-o zuul-build-merge-conflict'
      } else {
        iconGlyph = 'pficon pficon-error-circle-o'
      }
    }
    const icon = (
      <span
        className={'zuul-build-status ' + iconGlyph}
        title={iconTitle} />
    )
    if (item.live) {
      return (
        <Link to={this.props.tenant.linkPrefix + '/status/change/' + getRef(item).id}>
          {icon}
        </Link>
      )
    } else {
      return icon
    }
  }

  renderLineImg(item, i) {
    let image = this.props.preferences.darkMode ? LineTDarkImage : LineTImage
    if (item._tree_branches.indexOf(i) === item._tree_branches.length - 1) {
      // Angle line
      image = this.props.preferences.darkMode ? LineAngleDarkImage : LineAngleImage
    }
    return <img alt="Line" src={image} style={{ verticalAlign: 'baseline' }} />
  }

  render() {
    const { item, queue, expanded, pipeline, user, tenant } = this.props
    let row = []
    let adminMenuWidth = 15
    let i
    for (i = 0; i < queue._tree_columns; i++) {
      let className = ''
      if (i < item._tree.length && item._tree[i] !== null) {
        if (this.props.preferences.darkMode) {
          className = ' zuul-change-row-line-dark'
        } else {
          className = ' zuul-change-row-line'
        }
      }
      let lineStyle = {}
      if (i === item._tree_index ||
          item._tree_branches.indexOf(i) !== -1) {
        // Icon or line image: leave a gap
        lineStyle = {backgroundPositionY: '15px'}
      }
      row.push(
        <td key={i} className={'zuul-change-row' + className} style={lineStyle}>
          {i === item._tree_index ? this.renderStatusIcon(item) : ''}
          {item._tree_branches.indexOf(i) !== -1 ? (
            this.renderLineImg(item, i)) : ''}
        </td>)
    }
    let itemWidth = (user.isAdmin && user.scope.indexOf(tenant.name) !== -1)
      ? 360 - adminMenuWidth - 16 * queue._tree_columns
      : 360 - 16 * queue._tree_columns
    row.push(
      <td key={i + 1}
        className="zuul-change-cell"
        style={{ width: itemWidth + 'px' }}>
        <ItemPanel item={item} globalExpanded={expanded} pipeline={pipeline} />
      </td>
    )
    if (user.isAdmin && user.scope.indexOf(tenant.name) !== -1) {
      row.push(
        <td key={i + 2}
          style={{ verticalAlign: 'top', width: adminMenuWidth + 'px' }}>
          {this.renderAdminCommands(i + 2)}
        </td>
      )
    }

    return (
      <>
        <table className="zuul-change-box" style={{ boxSizing: 'content-box' }}>
          <tbody>
            <tr>{row}</tr>
          </tbody>
        </table>
        {this.renderDequeueModal()}
        {this.renderPromoteModal()}
      </>
    )
  }
}

export default connect(state => ({
  tenant: state.tenant,
  user: state.user,
  preferences: state.preferences,
}))(Item)
