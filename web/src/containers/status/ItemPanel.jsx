// Copyright 2018 Red Hat, Inc
// Copyright 2024 Acme Gating, LLC
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
import * as moment from 'moment'
import 'moment-duration-format'
import { Button } from '@patternfly/react-core'

import {
  calculateQueueItemTimes,
  ChangeLink,
  getJobStrResult,
  QueueItemProgressbar,
} from './Misc'
import { formatTime } from '../../Misc'

function getRefs(item) {
  // For backwards compat: get a list of this items refs.
  return 'refs' in item ? item.refs : [item]
}

class ItemPanel extends React.Component {
  static propTypes = {
    globalExpanded: PropTypes.bool.isRequired,
    item: PropTypes.object.isRequired,
    tenant: PropTypes.object,
    preferences: PropTypes.object
  }

  constructor () {
    super()
    this.state = {
      expanded: false,
      showSkipped: false,
    }
    this.onClick = this.onClick.bind(this)
    this.toggleSkippedJobs = this.toggleSkippedJobs.bind(this)
    this.clicked = false
  }

  onClick (e) {
    // Skip middle mouse button
    if (e.button === 1) {
      return
    }
    let expanded = this.state.expanded
    if (!this.clicked) {
      expanded = this.props.globalExpanded
    }
    this.clicked = true
    this.setState({ expanded: !expanded })
  }

  enqueueTime (ms) {
    // Special format case for enqueue time to add style
    let hours = 60 * 60 * 1000
    let now = Date.now()
    let delta = now - ms
    let status = 'text-success'
    let text = formatTime(delta)
    if (delta > (4 * hours)) {
      status = 'text-danger'
    } else if (delta > (2 * hours)) {
      status = 'text-warning'
    }
    return <span className={status}>{text}</span>
  }

  renderTimer (change, times) {
    let remainingTime
    if (times.remaining === null) {
      remainingTime = 'unknown'
    } else {
      remainingTime = formatTime(times.remaining)
    }
    return (
      <React.Fragment>
        <small title='Elapsed Time' className='time' style={{display: 'inline'}}>
          {this.enqueueTime(change.enqueue_time)}
        </small>
        <small> | </small>
        <small title='Remaining Time' className='time' style={{display: 'inline'}}>
          {remainingTime}
        </small>
      </React.Fragment>
    )
  }

  renderJobProgressBar (job, elapsedTime, remainingTime) {
    let progressPercent = 100 * (elapsedTime / (elapsedTime +
                                                remainingTime))
    // Show animation in preparation phase
    let className = ''
    let progressWidth = progressPercent
    let title = ''
    let remaining = remainingTime
    if (Number.isNaN(progressPercent)) {
      progressWidth = 100
      progressPercent = 0
      className = 'progress-bar-striped progress-bar-animated'
    } else if (job.pre_fail) {
      className = 'progress-bar-danger'
      title += 'Early failure detected.\n'
    }
    if (remaining !== null) {
      title += 'Estimated time remaining: ' + moment.duration(remaining).format({
        template: 'd [days] h [hours] m [minutes] s [seconds]',
        largest: 2,
        minValue: 30,
      })
    }

    return (
      <div className={`progress zuul-job-result${this.props.preferences.darkMode ? ' progress-dark' : ''}`}
        title={title}>
        <div className={'progress-bar ' + className}
          role='progressbar'
          aria-valuenow={progressPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          style={{'width': progressWidth + '%'}}
        />
      </div>
    )
  }

  renderJobStatusLabel (job, result) {
    let className, title
    switch (result) {
      case 'success':
        className = 'label-success'
        break
      case 'failure':
        className = 'label-danger'
        break
      case 'unstable':
      case 'retry_limit':
      case 'post_failure':
      case 'node_failure':
        className = 'label-warning'
        break
      case 'paused':
      case 'skipped':
        className = 'label-info'
        break
      case 'waiting':
        className = 'label-default'
        if (job.waiting_status !== null) {
          title = 'Waiting on ' + job.waiting_status
        }
        break
      case 'queued':
        className = 'label-default'
        if (job.waiting_status !== null) {
          title = 'Waiting on ' + job.waiting_status
        }
        break
      // 'in progress' 'lost' 'aborted' ...
      default:
        className = 'label-default'
    }

    return (
      <span className={'zuul-job-result label ' + className} title={title}>{result}</span>
    )
  }

  renderJob (job, job_times) {
    const { tenant } = this.props
    let job_name = job.name
    let ordinal_rules = new Intl.PluralRules('en', {type: 'ordinal'})
    const suffixes = {
      one: 'st',
      two: 'nd',
      few: 'rd',
      other: 'th'
    }
    if (job.tries > 1) {
        job_name = job_name + ' (' + job.tries + suffixes[ordinal_rules.select(job.tries)] + ' attempt)'
    }
    let name = ''
    if (job.result !== null) {
      name = <a className='zuul-job-name' href={job.report_url}>{job_name}</a>
    } else if (job.url !== null) {
      let url = job.url
      if (job.url.match('stream/')) {
        const to = (
          tenant.linkPrefix + '/' + job.url
        )
        name = <Link className='zuul-job-name' to={to}>{job_name}</Link>
      } else {
        name = <a className='zuul-job-name' href={url}>{job_name}</a>
      }
    } else {
      name = <span className='zuul-job-name'>{job_name}</span>
    }
    let resultBar
    let result = getJobStrResult(job)
    if (result === 'in progress') {
      resultBar = this.renderJobProgressBar(job, job_times.elapsed, job_times.remaining)
    } else {
      resultBar = this.renderJobStatusLabel(job, result)
    }

    return (
      <span>
        {name}
        {resultBar}
        {job.voting === false ? (
          <small className='zuul-non-voting-desc'> (non-voting)</small>) : ''}
        <div style={{clear: 'both'}} />
      </span>)
  }

  toggleSkippedJobs (e) {
    // Skip middle mouse button
    if (e.button === 1) {
      return
    }
    this.setState({ showSkipped: !this.state.showSkipped })
  }

  renderJobList (jobs, times) {
    const [buttonText, interestingJobs] = this.state.showSkipped ?
          ['Hide', jobs] :
          ['Show', jobs.filter(j => getJobStrResult(j) !== 'skipped')]
    const skippedJobCount = jobs.length - interestingJobs.length

    return (
      <>
        <ul className={`list-group ${this.props.preferences.darkMode ? 'zuul-patchset-body-dark' : 'zuul-patchset-body'}`}>
          {interestingJobs.map((job, idx) => (
            <li key={idx} className={`list-group-item ${this.props.preferences.darkMode ? 'zuul-change-job-dark' : 'zuul-change-job'}`}>
              {this.renderJob(job, times.jobs[job.name])}
            </li>
          ))}
          {(this.state.showSkipped || skippedJobCount) ? (
            <li key='last' className='list-group-item zuul-change-job'>
              <Button variant="link" className='zuul-skipped-jobs-button'
                      onClick={this.toggleSkippedJobs}>
                {buttonText} {skippedJobCount ? skippedJobCount : ''} skipped job{skippedJobCount === 1 ? '' : 's'}
              </Button>
            </li>
          ) : ''}
        </ul>
      </>
    )
  }

  render () {
    const { expanded } = this.state
    const { item, globalExpanded } = this.props
    let expand = globalExpanded
    if (this.clicked) {
      expand = expanded
    }
    const times = calculateQueueItemTimes(item)
    const header = (
      <div className={`panel panel-default ${this.props.preferences.darkMode ? 'zuul-change-dark' : 'zuul-change'}`}>
        <div className={`panel-heading ${this.props.preferences.darkMode ? 'zuul-patchset-header-dark' : 'zuul-patchset-header'}`}
          onClick={this.onClick}>
          <div>
            {item.live === true ? (
              <div className='row'>
                <div className='col-xs-6'>
                  <QueueItemProgressbar item={item} />
                </div>
                <div className='col-xs-6 text-right'>
                  {this.renderTimer(item, times)}
                </div>
              </div>
            ) : ''}
            {getRefs(item).map((change, idx) => (
              <div key={idx} className='row'>
                <div className='col-xs-8'>
                  <span className='change_project'>{change.project}</span>
                </div>
                <div className='col-xs-4 text-right'>
                  <ChangeLink change={change} />
                </div>
              </div>
            ))}
          </div>
        </div>
        {expand ? this.renderJobList(item.jobs, times) : ''}
      </div >
    )
    return (
      <React.Fragment>
        {header}
      </React.Fragment>
    )
  }
}

export default connect(state => ({
  tenant: state.tenant,
  preferences: state.preferences,
}))(ItemPanel)
