// Copyright 2020 BMW Group
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
  Flex,
  FlexItem,
  Switch,
} from '@patternfly/react-core'
import {
  AngleDownIcon,
  AngleRightIcon,
  OutlinedClockIcon
} from '@patternfly/react-icons'
import 'moment-duration-format'
import * as moment from 'moment'

import { BuildResult, BuildResultWithIcon } from './Misc'
import { IconProperty } from '../../Misc'

class BuildList extends React.Component {
  static propTypes = {
    builds: PropTypes.array,
    tenant: PropTypes.object,
  }

  // TODO (felix): Add a property "isCompact" to be used on the buildresult
  // page. Without this flag we might then even use this (with more
  // information) on the /builds page.

  constructor(props) {
    super(props)
    const { builds } = this.props
    let retriedJobs = builds.filter((build) => {
      return !build.final
    }).map((build) => (build.job_name)
    ).filter((build, idx, self) => {
      return self.indexOf(build) === idx
    })

    let skippedJobs = builds.filter((build) => {
      return build.result === 'SKIPPED'
    }).map((build) => (build.job_name)
    ).filter((build, idx, self) => {
      return self.indexOf(build) === idx
    })

    this.state = {
      visibleNonFinalBuilds: retriedJobs,
      retriedJobs: retriedJobs,
      skippedJobs: skippedJobs,
      showSkipped: false,
    }
  }

  sortedBuilds = () => {
    const { builds } = this.props
    const { visibleNonFinalBuilds, showSkipped } = this.state

    return builds.sort((a, b) => {
      // Group builds by job name, then order by decreasing start time; this will ensure retries are together
      if (a.job_name === b.job_name) {
        if (a.start_time < b.start_time) {
          return 1
        }
        if (a.start_time > b.start_time) {
          return -1
        }
        return 0
      }
      if (a.job_name > b.job_name) {
        return 1
      } else {
        return -1
      }
    }).filter((build) => {
      if (build.final || visibleNonFinalBuilds.indexOf(build.job_name) >= 0) {
        if (build.result === 'SKIPPED' && !showSkipped) {
          return false
        }
        return true
      }
      else {
        return false
      }
    })
  }

  handleFinalSwitch = isChecked => {
    const { retriedJobs } = this.state
    this.setState({ visibleNonFinalBuilds: (isChecked ? retriedJobs : []) })
  }

  handleSkippedSwitch = isChecked => {
    this.setState({ showSkipped: isChecked })
  }

  handleToggleVisibleNonFinalBuilds = (jobName) => {
    const { visibleNonFinalBuilds } = this.state
    const index = visibleNonFinalBuilds.indexOf(jobName)
    const newVisible =
      index >= 0 ? [...visibleNonFinalBuilds.slice(0, index), ...visibleNonFinalBuilds.slice(index + 1, visibleNonFinalBuilds.length)] : [...visibleNonFinalBuilds, jobName]
    this.setState({
      visibleNonFinalBuilds: newVisible,
    })
  }

  renderRetriesButton = (build, hasRetries) => {
    const { visibleNonFinalBuilds } = this.state
    if (!build.final || !hasRetries) {
      return <DataListCell key={`${build.uuid}-final`} width={1} isIcon={true}>
        {/* Hide the icon to maintain alignment between final and non-final elements */}
        <AngleRightIcon visibility="hidden" />
      </DataListCell >
    }
    const isExpanded = (visibleNonFinalBuilds.indexOf(build.job_name) >= 0)
    const RetryIcon =
      isExpanded
        ? AngleDownIcon
        : AngleRightIcon
    const retryAltText =
      isExpanded
        ? 'Hide retries for this job'
        : 'Show retries for this job'
    // TODO either replace this with an ExpandableSection (but this breaks the layout) or figure out CSS animations for the icon.
    return (
      <DataListCell key={`${build.uuid}-final`} width={1} isIcon={true}>
        <RetryIcon
          onClick={() => { this.handleToggleVisibleNonFinalBuilds(build.job_name) }}
          title={retryAltText}
          style={{ cursor: 'pointer' }} />
      </DataListCell >
    )
  }

  render() {
    const { tenant } = this.props
    const { visibleNonFinalBuilds, retriedJobs, skippedJobs, showSkipped } = this.state

    let retrySwitch = retriedJobs.length > 0 ?
      <FlexItem align={{ default: 'alignRight' }}>
        <span>Show retries &nbsp;</span>
        <Switch
          isChecked={visibleNonFinalBuilds === retriedJobs}
          onChange={this.handleFinalSwitch}
          isReversed
        />
      </FlexItem> :
      <></>

    let skippedSwitch = skippedJobs.length > 0 ?
      <FlexItem align={{ default: 'alignRight' }}>
        <span>Show skipped jobs &nbsp;</span>
        <Switch
          isChecked={showSkipped}
          onChange={this.handleSkippedSwitch}
          isReversed
        />
      </FlexItem> :
      <></>

    const sortedBuilds = this.sortedBuilds()

    return (
      <Flex direction={{ default: 'column' }}>
        {skippedSwitch}
        {retrySwitch}
        <FlexItem>
          <DataList
            className="zuul-build-list"
            isCompact
            style={{ fontSize: 'var(--pf-global--FontSize--md)' }}
          >
            {sortedBuilds.map((build) => {
              function linkWrap(cell) {
                return (<Link
                  to={`${tenant.linkPrefix}/build/${build.uuid}`}
                  style={{
                    textDecoration: 'none',
                    color: build.voting
                      ? 'inherit'
                      : 'var(--pf-global--disabled-color--100)',
                  }}
                >
                  {cell}
                </Link>)
              }
              return (
                <DataListItem key={build.uuid || build.job_name} id={build.uuid}>
                  <DataListItemRow
                    style={!build.final ? { backgroundColor: 'var(--pf-global--BackgroundColor--light-200)' } : {}}>
                    <DataListItemCells
                      dataListCells={[
                        this.renderRetriesButton(build, retriedJobs.indexOf(build.job_name) >= 0),
                        <DataListCell key={build.uuid} width={3}>
                          {linkWrap(<BuildResultWithIcon
                            result={build.result}
                            colored={build.voting}
                            size="sm"
                          >
                            {build.job_name}
                            {!build.voting && ' (non-voting)'}
                          </BuildResultWithIcon>)}
                        </DataListCell>,
                        <DataListCell key={`${build.uuid}-time`}>
                          {linkWrap(<IconProperty
                            icon={<OutlinedClockIcon />}
                            value={moment
                              .duration(build.duration, 'seconds')
                              .format('h [hr] m [min] s [sec]')}
                          />)}
                        </DataListCell>,
                        <DataListCell key={`${build.uuid}-result`}>
                          {linkWrap(<BuildResult
                            result={build.result}
                            colored={build.voting}
                          />)}
                        </DataListCell>,
                      ]}
                    />
                  </DataListItemRow>
                </DataListItem>
              )
            })}
          </DataList>
        </FlexItem>
      </Flex>
    )
  }
}

export default connect((state) => ({ tenant: state.tenant }))(BuildList)
