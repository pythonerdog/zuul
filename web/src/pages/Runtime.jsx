// Copyright 2022 Acme Gating, LLC
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

import React, { useEffect, useState, useCallback } from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import { useHistory, useLocation } from 'react-router-dom'
import {
  PageSection,
  PageSectionVariants,
  Text,
  TextContent,
} from '@patternfly/react-core'
import { fetchBuildTimes } from '../api'
import {
  Chart,
  ChartAxis,
  ChartScatter,
  ChartThemeColor,
  ChartThemeVariant,
  ChartVoronoiContainer,
  getCustomTheme,
} from '@patternfly/react-charts'
import * as moment from 'moment'
import * as moment_tz from 'moment-timezone'

import FreezeJobToolbar from '../containers/freezejob/FreezeJobToolbar'

/* This should be able to be removed in PF5 due to built in theming /*
   Reference for keys:
   https://github.com/patternfly/patternfly-react/blob/62ec17cdac823d3f993c04bb3b22c2811dec4cb7/packages/react-charts/src/components/ChartTheme/themes/base-theme.ts
*/
const DarkTheme={
  axis: {
    style: {
      grid: {
        stroke: '#e0e0e0',
      },
      ticks: {
        stroke: '#e0e0e0',
      },
      axis: {
        stroke: '#e0e0e0',
      },
      axisLabel: {
        stroke: '#e0e0e0',
      },
      tickLabels: {
        stroke: '#e0e0e0',
      },
    },
  },
  legend: {
    style: {
      labels: {
        stroke: '#e0e0e0',
      },
    },
  },
  scatter: {
    style: {
      labels: {
        fill: '#e0e0e0',
        stroke: '#e0e0e0',
      },
    },
  },
}

const LightTheme={
  axis: {
    style: {
      grid: {
        stroke: '#ccc',
      },
      ticks: {
        stroke: '#ccc',
      },
    },
  },
}

function toTime(x, tz) {
  return moment_tz.utc(new Date(x)).tz(tz)
}

function TestChart(builds, preferences, timezone) {
  const myTheme = getCustomTheme(ChartThemeColor.blue, ChartThemeVariant.light,
                                 preferences.darkMode ? DarkTheme : LightTheme)
  let results = {SUCCESS: [], FAILURE: []}
  builds.forEach(build => {
    if (results[build.result] === undefined) {
      results[build.result] = []
    }
    results[build.result].push({
      name: toTime(build.end_time, timezone),
      x: toTime(build.end_time, timezone),
      y: build.duration,
      y_human: moment.duration(build.duration, 'seconds').format('h[h]m[m]s[s]'),
    })
  })
  const title = `Runtimes of ${builds[0].job_name} on ${builds[0].project}@${builds[0].branch}`

  return (
  <div>
    <TextContent>
      <Text component="h2" style={{paddingLeft: 50}}>
        {title}
      </Text>
    </TextContent>
    <Chart
      ariaTitle={title}
      containerComponent={<ChartVoronoiContainer labels={({ datum }) => `${datum.name}: ${datum.y_human}`} constrainToVisibleArea />}
      legendData={[{ name: 'Success' }, { name: 'Failure' }]}
      legendOrientation="vertical"
      legendPosition="right"
      height={500}
      name="chart1"
      theme={myTheme}
      padding={{
        bottom: 50,
        left: 100,  // Adjusted to accommodate axis
        right: 100, // Adjusted to accommodate legend
        top: 10
      }}
      width={1200}
      scale={{x: 'time', y: 'linear'}}
    >
      <ChartAxis
        tickValues={[toTime(builds[0].end_time, timezone),
                     toTime(builds.slice(-1)[0].end_time, timezone)]}
        tickFormat={(t) => t.format('YYYY-MM-DD')}
      />
      <ChartAxis
        dependentAxis
        tickFormat={(t) => moment.duration(t, 'seconds').format('h[h]m[m]s[s]')}
      />
      <ChartScatter
        data={results['SUCCESS']}
        style={{data: {fill: '#0066cc'}}}
      />
      <ChartScatter
        data={results['FAILURE']}
        style={{data: {fill: '#8bc1f7'}}}
      />
    </Chart>
  </div>
  )
}


function RuntimePage(props) {
  const { tenant, preferences, timezone } = props

  const [currentPipeline, setCurrentPipeline] = useState()
  const [currentProject, setCurrentProject] = useState()
  const [currentBranch, setCurrentBranch] = useState()
  const [currentJobName, setCurrentJobName] = useState()
  const [buildList, setBuildList] = useState()
  const history = useHistory()
  const location = useLocation()

  if (!currentBranch) {
    const urlParams = new URLSearchParams(location.search)
    const pipeline = urlParams.get('pipeline')
    const project = urlParams.get('project')
    const branch = urlParams.get('branch')
    const job_name = urlParams.get('job_name')
    if (pipeline && branch && project && job_name) {
      setCurrentPipeline(pipeline)
      setCurrentProject(project)
      setCurrentBranch(branch)
      setCurrentJobName(job_name)
    }
  }

  const updateData = useCallback(() => {
    const queryString=`&pipeline=${currentPipeline}&project=${currentProject}&branch=${currentBranch}&job_name=${currentJobName}`
    fetchBuildTimes(tenant.apiPrefix, queryString).then((response) => {
      const { compare } = Intl.Collator('en-US')
      const builds = response.data
      builds.sort((a, b) => compare(a.end_time, b.end_time))
      setBuildList(builds)
    })
  }, [currentPipeline, currentProject,
      currentBranch, currentJobName, tenant.apiPrefix])

  useEffect(() => {
    document.title = 'Zuul Job Runtimes'
    if (currentPipeline && currentProject && currentBranch && currentJobName) {
      updateData()
    }
  }, [updateData, tenant, currentPipeline, currentProject,
      currentBranch, currentJobName])

  function onChange(pipeline, project, branch, job_name) {
    setCurrentPipeline(pipeline)
    setCurrentProject(project)
    setCurrentBranch(branch)
    setCurrentJobName(job_name)

    const searchParams = new URLSearchParams('')
    searchParams.append('pipeline', pipeline)
    searchParams.append('project', project)
    searchParams.append('branch', branch)
    searchParams.append('job_name', job_name)
    history.push({
      pathname: location.pathname,
      search: searchParams.toString(),
    })
  }

  function renderBuilds(builds) {
    if (builds && builds.length > 0) {
      return (TestChart(builds, preferences, timezone))
    } else {
      return <></>
    }
  }

  return (
    <>
      <PageSection variant={PageSectionVariants.light}>
        <TextContent>
          <Text component="h1">Job Runtimes</Text>
        </TextContent>
        <FreezeJobToolbar
          onChange={onChange}
          defaultPipeline={currentPipeline}
          defaultProject={currentProject}
          defaultBranch={currentBranch}
          defaultJob={currentJobName}
          buttonText="Fetch"
        />
        <>
          {renderBuilds(buildList)}
        </>
      </PageSection>
    </>
  )
}

RuntimePage.propTypes = {
  tenant: PropTypes.object,
  preferences: PropTypes.object,
  timezone: PropTypes.string,
}

function mapStateToProps(state) {
  return {
    tenant: state.tenant,
    preferences: state.preferences,
    timezone: state.timezone,
  }
}

export default connect(mapStateToProps)(RuntimePage)
