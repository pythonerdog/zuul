// Copyright 2021 Red Hat, Inc
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

import * as moment from 'moment'
import * as moment_tz from 'moment-timezone'
import 'moment-duration-format'

import { Chart, ChartBar, ChartAxis, ChartLegend, ChartTooltip } from '@patternfly/react-charts'

import { buildResultLegendData, buildsBarStyle } from './Misc'
import { describeRef } from '../../Misc'


function BuildsetGanttChart(props) {
    const { builds, timezone, preferences } = props
    const sortedByStartTime = builds.sort((a, b) => {
        if (a.start_time > b.start_time) {
            return -1
        }
        if (a.start_time < b.start_time) {
            return 1
        }
        return 0
    })
    const origin = moment_tz.utc(sortedByStartTime[builds.length - 1].start_time).tz(timezone)

    const longestJobName = builds.reduce((a, build) => (a.length < build.job_name.length ? build.job_name : a), '')
    const jobNames = builds.map((d) => d.job_name)

    const data = sortedByStartTime.map((build) => {
        return {
            x: build.uuid,
            y0: build.start_time ? (moment_tz.utc(build.start_time).tz(timezone) - origin) / 1000 : 0,
            y: build.end_time ? (moment_tz.utc(build.end_time).tz(timezone) - origin) / 1000 : 0,
            result: build.result,
            started: moment_tz.utc(build.start_time).tz(timezone).format('YYYY-MM-DD HH:mm:ss'),
            ended: moment_tz.utc(build.end_time).tz(timezone).format('YYYY-MM-DD HH:mm:ss'),
            ref: build.ref,
        }
    })

    const legendData = builds.map((build) => (
        build.result
    )).filter((result, idx, self) => { return self.indexOf(result) === idx }
    ).map((legend) => ({ name: legend }))

    const uniqueResults = builds.map(
        (build) => (build.result)
    ).filter((result, idx, self) => {
        return self.indexOf(result) === idx
    })

    const chartLegend = buildResultLegendData.filter((legend) => { return uniqueResults.indexOf(legend.name) > -1 })

    let horizontalLegendTextColor = '#000'
    if (preferences.darkMode) {
      horizontalLegendTextColor = '#ccc'
    }

    return (
        <div style={{ height: Math.max(400, 20 * builds.length) + 'px', width: '900px' }}>
            <Chart
                horizontal
                domainPadding={{ x: 20 }}
                width={750}
                height={Math.max(400, 20 * builds.length)}
                padding={{
                    bottom: 80,
                    left: 8 * longestJobName.length,
                    right: 80,
                    top: 80,
                }}
                legendOrientation='horizontal'
                legendPosition='top'
                legendData={legendData}
                legendComponent={<ChartLegend data={chartLegend} itemsPerRow={4} style={{labels: {fill: horizontalLegendTextColor}}} />}
            >
              <ChartAxis
                style={{tickLabels: {fill:horizontalLegendTextColor}}}
                tickFormat={((tick, index) => jobNames[index])}
              />
                <ChartAxis
                    dependentAxis
                    showGrid
                    tickFormat={(t) => {
                        let format
                        switch (true) {
                            case (t < 180):
                                format = 's [sec]'
                                break
                            case (t < 7200):
                                format = 'm [min]'
                                break
                            default:
                                format = 'h [hr] m [min]'
                        }
                        return moment.duration(t, 'seconds').format(format)
                    }}
                    fixLabelOverlap={true}
                    style={{ tickLabels: { angle: -25, padding: 1, verticalAnchor: 'middle', textAnchor: 'end', fill: horizontalLegendTextColor } }}
                />
                <ChartBar
                    data={data}
                    style={ buildsBarStyle }
                    labelComponent={
                        <ChartTooltip constrainToVisibleArea/>}
                    labels={({ datum }) => `${datum.result}\nStarted ${datum.started}\nEnded ${datum.ended}\n${describeRef(datum.ref)}`}
                />
            </Chart>
        </div>
    )

}

BuildsetGanttChart.propTypes = {
    builds: PropTypes.array.isRequired,
    timezone: PropTypes.string,
    preferences: PropTypes.object,
}

export default connect((state) => ({
    timezone: state.timezone,
    preferences: state.preferences,
}))(BuildsetGanttChart)
