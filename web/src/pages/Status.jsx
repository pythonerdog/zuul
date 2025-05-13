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

import * as moment from 'moment-timezone'
import * as React from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import {
  Checkbox,
  Icon,
  Form,
  FormGroup,
  FormControl,
} from 'patternfly-react'
import { PageSection, PageSectionVariants } from '@patternfly/react-core'

import { fetchStatusIfNeeded } from '../actions/status'
import Pipeline from '../containers/status/Pipeline'
import { Fetchable } from '../containers/Fetching'
import { removeHash } from '../Misc'


class StatusPage extends React.Component {
  static propTypes = {
    location: PropTypes.object,
    tenant: PropTypes.object,
    preferences: PropTypes.object,
    timezone: PropTypes.string,
    remoteData: PropTypes.object,
    dispatch: PropTypes.func
  }

  state = {
    filter: null,
    expanded: false,
  }

  visibilityListener = () => {
    if (document[this.visibilityStateProperty] === 'visible') {
      this.visible = true
      this.updateData()
    } else {
      this.visible = false
    }
  }

  constructor () {
    super()

    this.timer = null
    this.visible = true

    // Stop refresh when page is not visible
    if (typeof document.hidden !== 'undefined') {
      this.visibilityChangeEvent = 'visibilitychange'
      this.visibilityStateProperty = 'visibilityState'
    } else if (typeof document.mozHidden !== 'undefined') {
      this.visibilityChangeEvent = 'mozvisibilitychange'
      this.visibilityStateProperty = 'mozVisibilityState'
    } else if (typeof document.msHidden !== 'undefined') {
      this.visibilityChangeEvent = 'msvisibilitychange'
      this.visibilityStateProperty = 'msVisibilityState'
    } else if (typeof document.webkitHidden !== 'undefined') {
      this.visibilityChangeEvent = 'webkitvisibilitychange'
      this.visibilityStateProperty = 'webkitVisibilityState'
    }
    document.addEventListener(
      this.visibilityChangeEvent, this.visibilityListener, false)
  }

  updateData = (force) => {
    if (force || (this.visible && this.props.preferences.autoReload)) {
      this.props.dispatch(fetchStatusIfNeeded(this.props.tenant))
        .then(() => {if (this.props.preferences.autoReload && this.visible) {
          this.timer = setTimeout(this.updateData, 5000)
        }})
    }
    // Clear any running timer
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
  }

  componentDidMount () {
    document.title = 'Zuul Status'
    this.loadState()
    if (this.props.tenant.name) {
      this.updateData(true)
    }
    window.addEventListener('storage', this.loadState)
  }

  componentDidUpdate (prevProps) {
    if (this.props.tenant.name !== prevProps.tenant.name) {
      this.updateData(true)
    }
    // If the user just enabled auto-reload
    if (this.props.preferences.autoReload &&
        !prevProps.preferences.autoReload &&
        !this.timer) {
      this.updateData(true)
    }
  }

  componentWillUnmount () {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
    this.visible = false
    document.removeEventListener(
      this.visibilityChangeEvent, this.visibilityListener)
  }

  setFilter = (filter) => {
    // Update form ref value
    this.filter.value = filter
    // Store value in location
    if (filter) {
      window.location.hash = '#' + filter
    } else {
      removeHash()
    }
    this.setState({filter: filter})
  }

  handleKeyPress = (e) => {
    if (e.charCode === 13) {
      this.setFilter(e.target.value)
      e.preventDefault()
      e.target.blur()
    }
  }

  handleCheckBox = (e) => {
    this.setState({expanded: e.target.checked})
    localStorage.setItem('zuul_expand_by_default', e.target.checked)
  }

  loadState = () => {
    const filter = this.props.location.hash ? this.props.location.hash.slice(1) : null
    let expanded = localStorage.getItem('zuul_expand_by_default') || false
    if (typeof expanded === 'string') {
      expanded = (expanded === 'true')
    }
    if (filter || expanded) {
      this.setState({
        filter: filter,
        expanded: expanded
      })
    }
  }

  renderStatusHeader (status) {
    return (
      <p>
        Queue lengths: <span>{status.trigger_event_queue ?
          status.trigger_event_queue.length : '0'
        }</span> events,&nbsp;
        <span>{status.management_event_queue ?
          status.management_event_queue.length : '0'
        }</span> management events.
      </p>
    )
  }

  renderStatusFooter (status) {
    return (
      <React.Fragment>
        <p>Zuul version: <span>{status.zuul_version}</span></p>
        {status.last_reconfigured ? (
          <p>Last reconfigured: <span>
            {moment.utc(status.last_reconfigured).tz(this.props.timezone).format('llll')}
          </span></p>) : ''}
      </React.Fragment>
    )
  }

  render () {
    const { remoteData } = this.props
    const { filter, expanded } = this.state
    const status = remoteData.status
    const statusControl = (
      <Form inline>
        <FormGroup controlId='status'>
          <FormControl
            type='text'
            className="pf-c-form-control"
            placeholder='change or project name'
            defaultValue={filter}
            inputRef={i => this.filter = i}
            onKeyPress={this.handleKeyPress} />
          {filter && (
            <FormControl.Feedback>
              <span
                onClick={() => {this.setFilter('')}}
                style={{cursor: 'pointer', zIndex: 10, pointerEvents: 'auto'}}
              >
                <Icon type='pf' title='Clear filter' name='delete' />
              &nbsp;
              </span>
            </FormControl.Feedback>
          )}
        </FormGroup>
        <FormGroup controlId='status'>
          &nbsp; Expand by default:&nbsp;
          <Checkbox
            defaultChecked={expanded}
            onChange={this.handleCheckBox} />
        </FormGroup>
      </Form>
    )
    return (
      <PageSection variant={this.props.preferences.darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
        <div style={{display: 'flex', float: 'right'}}>
          <Fetchable
            isFetching={remoteData.isFetching}
            fetchCallback={this.updateData}
          />
        </div>

        {status && this.renderStatusHeader(status)}
        {statusControl}
        <div className='row zuul-status-content'>
          {status && status.pipelines.map(item => (
            <Pipeline
              pipeline={item}
              filter={filter}
              expanded={expanded}
              key={item.name}
            />
          ))}
        </div>
        {status && this.renderStatusFooter(status)}
      </PageSection>)
  }
}

export default connect(state => ({
  preferences: state.preferences,
  tenant: state.tenant,
  timezone: state.timezone,
  remoteData: state.status,
}))(StatusPage)
