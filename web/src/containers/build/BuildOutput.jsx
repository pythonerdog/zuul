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
import { connect } from 'react-redux'
import { Fragment } from 'react'
import ReAnsi from '@softwarefactory-project/re-ansi'
import PropTypes from 'prop-types'
import {
  Card,
  CardBody,
  CardHeader,
  Chip,
  DataList,
  DataListItem,
  DataListItemRow,
  DataListItemCells,
  DataListCell,
  Divider,
  Label,
  Flex,
  FlexItem,
} from '@patternfly/react-core'

import {
  CheckCircleIcon,
  ContainerNodeIcon,
  TimesIcon,
  TimesCircleIcon,
} from '@patternfly/react-icons'

const ANSI_REGEX = new RegExp('\x33[[0-9;]+m')


class BuildOutputLabel extends React.Component {
  static propTypes = {
    ok: PropTypes.number,
    changed: PropTypes.number,
    failures: PropTypes.number,
  }

  render() {
    let color = this.props.failures ? 'red' : 'green'
    let icon = this.props.failures ? <TimesCircleIcon /> : <CheckCircleIcon />
    let failures = this.props.failures ? (
      <>
        <Divider orientation={{default: 'vertical'}} />
        <FlexItem><strong>{this.props.failures}</strong> Failure{this.props.failures > 1 ? 's' : ''}</FlexItem>
      </>
    ) : null

    return (
      <Label color={color} icon={icon}>
        <Flex>
          <FlexItem><strong>{this.props.ok}</strong> OK</FlexItem>
          <Divider orientation={{default: 'vertical'}} />
          <FlexItem><strong>{this.props.changed}</strong> Changed</FlexItem>
          { failures }
        </Flex>
      </Label>
    )
  }
}


class BuildOutput extends React.Component {
  static propTypes = {
    output: PropTypes.object,
    preferences: PropTypes.object,
  }

  renderHosts (hosts) {
    return (
      <>
        <br />
        <div className={'zuul-task-summary'}>
          <DataList aria-label="Build Results" isCompact={true}>
            {Object.entries(hosts).map(([host, values]) => (
              <DataListItem key={host} aria-label="Host">
                <DataListItemRow>
                  <DataListItemCells
                    dataListCells={[
                      <DataListCell key={host + '.name'}>
                        <Chip isReadOnly={true} textMaxWidth='50ch'>
                          <span style={{ fontSize: 'var(--pf-global--FontSize--md)' }}>
                            <ContainerNodeIcon />&nbsp;{host}
                          </span>
                        </Chip>
                      </DataListCell>,
                      <DataListCell key={host + '.data'} >
                        <BuildOutputLabel ok={values.ok} changed={values.changed} failures={values.failures} />
                      </DataListCell>
                    ]}
                  />
                </DataListItemRow>
              </DataListItem>
            ))}
          </DataList>
        </div>
      </>
    )
  }

  getLines(lines) {
    const max_lines = 42
    if (lines && lines.length > 0) {
      return [
        lines.slice(0, -max_lines).join('\n'),
        lines.slice(-max_lines).join('\n')
      ]
    }
    return ['', '']
  }

  renderFailedTask (host, task) {
    let zuulOutputClass = 'zuul-build-output'
    if (this.props.preferences.darkMode) {
      zuulOutputClass = 'zuul-build-output-dark'
    }
    const [stdout_early_lines, stdout_late_lines] = this.getLines(task.stdout_lines)
    const [stderr_early_lines, stderr_late_lines] = this.getLines(task.stderr_lines)
    // If there is an ANSI color escape string, set a white-on-black
    // color scheme so the output looks more like what we would expect in a console.
    let term_style = {}
    if (ANSI_REGEX.test(stdout_early_lines) ||
        ANSI_REGEX.test(stdout_late_lines) ||
        ANSI_REGEX.test(stderr_early_lines) ||
        ANSI_REGEX.test(stderr_late_lines)) {
      term_style = {backgroundColor: 'black', color: 'white'}
    }
    return (
      <Card key={host + task.zuul_log_id} className="zuul-task-summary-failed" style={this.props.preferences.darkMode ? {background: 'var(--pf-global--BackgroundColor--300)'} : {}}>
        <CardHeader>
          <TimesIcon style={{ color: 'var(--pf-global--danger-color--100)' }}/>
            &nbsp;Task&nbsp;<strong>{task.name}</strong>&nbsp;
            failed running on host&nbsp;<strong>{host}</strong>
        </CardHeader>
        <CardBody>
          {task.invocation && task.invocation.module_args &&
           task.invocation.module_args._raw_params && (
            <pre key="cmd" title="cmd" className={'cmd ' + zuulOutputClass}>
              {task.invocation.module_args._raw_params}
            </pre>
          )}
          {task.msg && (
            <pre key="msg" title="msg" className={zuulOutputClass}>{task.msg}</pre>
          )}
          {task.exception && (
            <pre key="exc" style={{ color: 'red' }} title="exc" className={zuulOutputClass}>{task.exception}</pre>
          )}
          {stdout_late_lines.length > 0 && (
            <Fragment>
              {stdout_early_lines.length > 0 && (
                <details className={`${'foldable'} ${'stdout'}`}><summary></summary>
                  <pre key="stdout" title="stdout" className={zuulOutputClass} style={term_style}>
                    <ReAnsi log={stdout_early_lines} />
                  </pre>
                </details>)}
              <pre key="stdout" title="stdout" className={zuulOutputClass} style={term_style}>
                <ReAnsi log={stdout_late_lines} />
              </pre>
            </Fragment>
          )}
          {stderr_late_lines.length > 0 && (
            <Fragment>
              {stderr_early_lines.length > 0 && (
                <details className={`${'foldable'} ${'stderr'}`}><summary></summary>
                  <pre key="stderr" title="stderr" className={zuulOutputClass} style={term_style}>
                    <ReAnsi log={stderr_early_lines} />
                  </pre>
                </details>
              )}
              <pre key="stderr" title="stderr" className={zuulOutputClass} style={term_style}>
                <ReAnsi log={stderr_late_lines} />
              </pre>
            </Fragment>
          )}
        </CardBody>
      </Card>
    )
  }

  render () {
    const { output } = this.props
    return (
      <React.Fragment>
        {this.renderHosts(output)}
        <br />
        {Object.entries(output)
          .filter(([, values]) => values.failed.length > 0)
          .map(([host, values]) => (values.failed.map(failed => (
            this.renderFailedTask(host, failed)))))}
      </React.Fragment>
    )
  }
}


function mapStateToProps(state) {
  return {
    preferences: state.preferences,
  }
}

export default connect(mapStateToProps)(BuildOutput)
