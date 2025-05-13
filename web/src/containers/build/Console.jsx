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

import * as moment from 'moment'
import 'moment-duration-format'
import * as React from 'react'
import ReAnsi from '@softwarefactory-project/re-ansi'
import PropTypes from 'prop-types'
import ReactJson from 'react-json-view'
import { connect } from 'react-redux'

import {
  Button,
  Chip,
  DataList,
  DataListItem,
  DataListItemRow,
  DataListCell,
  DataListItemCells,
  DataListToggle,
  DataListContent,
  Divider,
  Flex,
  FlexItem,
  Label,
  Modal,
  Tooltip
} from '@patternfly/react-core'

import {
  AngleRightIcon,
  ContainerNodeIcon,
  InfoCircleIcon,
  SearchPlusIcon,
  LinkIcon,
} from '@patternfly/react-icons'

import {
  hasInterestingKeys,
  findLoopLabel,
  shouldIncludeKey,
  makeTaskPath,
  taskPathMatches,
} from '../../actions/build'

const INTERESTING_KEYS = ['msg', 'cmd', 'stdout', 'stderr']
const ANSI_REGEX = new RegExp('\x33[[0-9;]+m')


class TaskOutput extends React.Component {
  static propTypes = {
    data: PropTypes.object,
    include: PropTypes.array,
    preferences: PropTypes.object,
  }

  renderResults(value) {
    const interesting_results = []

    // This was written to assume "value" is an array of key/value
    // mappings to output.  This seems to be a good assumption for the
    // most part, but "package:" on at least some distros --
    // RedHat/yum/dnf we've found -- outputs a result that is just an
    // array of strings with what packages were installed.  So, if we
    // see an array of strings as the value, we just swizzle that into
    // a key/value so it displays usefully.
    const isAllStrings = value.every(i => typeof i === 'string')
    if (isAllStrings) {
      value = [ {output: [...value]} ]
    }

    value.forEach((result, idx) => {
      const keys = Object.entries(result).filter(
        ([key, value]) => shouldIncludeKey(
          key, value, true, this.props.include))
      if (keys.length) {
        interesting_results.push(idx)
      }
    })

    return (
      <div key='results'>
        {interesting_results.length>0 &&
         <React.Fragment>
           <h5 key='results-header'>results</h5>
           {interesting_results.map((idx) => (
             <div className='zuul-console-task-result' key={idx}>
               <h4 key={idx}>{idx}: {findLoopLabel(value[idx])}</h4>
               {Object.entries(value[idx]).map(([key, value]) => (
                 this.renderData(key, value, true)
               ))}
             </div>
           ))}
         </React.Fragment>
        }
      </div>
    )
  }

  renderData(key, value, ignore_underscore) {
    let ret
    if (!shouldIncludeKey(key, value, ignore_underscore, this.props.include)) {
      return (<React.Fragment key={key}/>)
    }
    if (value === null) {
      ret = (
        <pre>
          null
        </pre>
      )
    } else if (typeof(value) === 'string') {
      // If there is an ANSI color escape string, set a white-on-black
      // color scheme so the output looks more like what we would expect in a console.
      const style = ANSI_REGEX.test(value) ? {backgroundColor: 'black', color: 'white'} : {}
      ret = (
        <pre style={style}>
          <ReAnsi log={value} />
        </pre>
      )
    } else if (typeof(value) === 'object') {
      ret = (
        <pre>
          <ReactJson
            src={value}
            name={null}
            sortKeys={true}
            enableClipboard={false}
            displayDataTypes={false}
            theme={this.props.preferences.darkMode ? 'tomorrow' : 'rjv-default'}/>
        </pre>
      )
    } else {
      ret = (
        <pre>
          {value.toString()}
        </pre>
      )
    }

    return (
      <div className={this.props.preferences.darkMode ? 'zuul-console-dark' : 'zuul-console-light'} key={key}>
        {ret && <h5>{key}</h5>}
        {ret && ret}
      </div>
    )
  }

  render () {
    const { data } = this.props

    return (
      <React.Fragment>
        {Object.entries(data).map(([key, value]) => (
          key==='results'?this.renderResults(value):this.renderData(key, value)
        ))}
      </React.Fragment>
    )
  }
}

class HostTask extends React.Component {
  static propTypes = {
    hostname: PropTypes.string,
    task: PropTypes.object,
    host: PropTypes.object,
    errorIds: PropTypes.object,
    taskPath: PropTypes.array,
    displayPath: PropTypes.array,
    preferences: PropTypes.object,
  }

  state = {
    showModal: false,
    failed: false,
    changed: false,
    skipped: false,
    ok: false
  }

  open = () => {
    this.setState({showModal: true})
  }

  close = () => {
    this.setState({showModal: false})
  }

  constructor (props) {
    super(props)

    const { host, taskPath, displayPath } = this.props

    if (host.failed) {
      this.state.failed = true
    } else if (host.changed) {
      this.state.changed = true
    } else if (host.skipped) {
      this.state.skipped = true
    } else {
      this.state.ok = true
    }

    if (taskPathMatches(taskPath, displayPath))
      this.state.showModal = true

    // If it has errors, expand by default
    this.state.expanded = this.props.errorIds.has(this.props.task.task.id)
  }

  render () {
    const { hostname, task, host, taskPath } = this.props
    const dataListCells = []

    // "interesting" result tasks are those that have some values in
    // their results that show command output, etc.  These plays get
    // an expansion that shows these values without having to click
    // and bring up the full insepction modal.
    const interestingKeys = hasInterestingKeys(host, INTERESTING_KEYS)

    let name = task.task.name
    if (!name) {
      name = host.action
    }
    if (task.role) {
      name = task.role.name + ': ' + name
    }

    dataListCells.push(
      <DataListCell key='name' width={4}>{name}</DataListCell>
    )

    let labelColor = null
    let labelString = null

    if (this.state.failed) {
      labelColor = 'red'
      labelString = 'Failed'
    } else if (this.state.changed) {
      labelColor = 'orange'
      labelString = 'Changed'
    } else if (this.state.skipped) {
      labelColor = 'grey'
      labelString = 'Skipped'
    } else if (this.state.ok) {
      labelColor = 'green'
      labelString = 'OK'
    }

    dataListCells.push(
      <DataListCell key='state'>
        <Tooltip content={<div>Click for details</div>}>
          <Label color={labelColor} onClick={this.open}
                 style={{cursor: 'pointer'}}>
            <Flex flexWrap={{default: 'nowrap' }}>
              <FlexItem style={{minWidth: '7ch'}}>
                {labelString}
              </FlexItem>
              <Divider align={{default: 'alignRight'}} orientation={{default: 'vertical'}} />
              <FlexItem>
                <SearchPlusIcon color='var(--pf-global--Color--200)' style={{cursor: 'pointer'}} />
              </FlexItem>
            </Flex>
          </Label>
        </Tooltip>
      </DataListCell>)

    dataListCells.push(
      <DataListCell key='node'>
        <Chip isReadOnly={true} textMaxWidth='50ch'>
          <span style={{ fontSize: 'var(--pf-global--FontSize--md)' }}>
          <ContainerNodeIcon />&nbsp;{hostname}</span>
        </Chip>
      </DataListCell>
    )

    let duration = moment.duration(
      moment(task.task.duration.end).diff(task.task.duration.start)
    ).format({
      template: 'h [hr] m [min] s [sec]',
      largest: 2,
      minValue: 1,
    })

    dataListCells.push(
      <DataListCell key='task-duration'>
        <span className='task-duration'>{duration}</span>
      </DataListCell>
    )

    const content = <TaskOutput data={this.props.host} include={INTERESTING_KEYS} preferences={this.props.preferences}/>

    let item = null
    if (interestingKeys) {
      item = <DataListItem
               isExpanded={this.state.expanded}
               className={this.state.failed ? 'zuul-console-task-failed' : ''}>
               <DataListItemRow>
                 <DataListToggle
                   onClick={() => {this.setState({expanded: !this.state.expanded})}}
                   isExpanded={this.state.expanded}
                 />
                 <DataListItemCells dataListCells={ dataListCells } />
               </DataListItemRow>
               <DataListContent
                 isHidden={!this.state.expanded}>
                 { content }
               </DataListContent>
             </DataListItem>
    } else {
      // We currently have to build the data-list item/row/control manually
      // as we don't have a way to hide the toggle.  Hopefully PF will
      // add a prop that does this so we can get rid of this, see:
      //   https://github.com/patternfly/patternfly/issues/5055
      item = <li className="pf-c-data-list__item">
               <div className="pf-c-data-list__item-row">
                 <div className="pf-c-data-list__item-control"
                      style={{visibility: 'hidden'}}>
                   <div className="pf-c-data-list__toggle">
                     <Button disabled>
                       <AngleRightIcon />
                     </Button>
                   </div>
                 </div>
                 <DataListItemCells dataListCells={ dataListCells } />
               </div>
             </li>
    }

    const modalDescription = <Flex>
                               <FlexItem>
                                 <Label color={labelColor}>{labelString}</Label>
                               </FlexItem>
                               <FlexItem>
                                 <Chip isReadOnly={true} textMaxWidth='50ch'>
                                   <span style={{ fontSize: 'var(--pf-global--FontSize--md)' }}>
                                   <ContainerNodeIcon />&nbsp;{hostname}</span>
                                 </Chip>
                               </FlexItem>
                               <FlexItem>
                                 <a href={'#'+makeTaskPath(taskPath)}>
                                   <LinkIcon name='link' title='Permalink' />
                                 </a>
                               </FlexItem>
                             </Flex>

    return (
      <>
        {item}
        <Modal
          title={name}
          isOpen={this.state.showModal}
          onClose={this.close}
          description={modalDescription}>
          <TaskOutput data={host} preferences={this.props.preferences}/>
        </Modal>
      </>
    )
  }
}

class PlayBook extends React.Component {
  static propTypes = {
    playbook: PropTypes.object,
    errorIds: PropTypes.object,
    taskPath: PropTypes.array,
    displayPath: PropTypes.array,
    preferences: PropTypes.object,
  }

  constructor(props) {
    super(props)
    this.state = {
      // Start the playbook expanded if
      //  * has errror in it
      //  * direct link
      //  * it is a run playbook
      expanded: (this.props.errorIds.has(this.props.playbook.phase + this.props.playbook.index) ||
                 taskPathMatches(this.props.taskPath, this.props.displayPath) ||
                 this.props.playbook.phase === 'run'),
      // NOTE(ianw) 2022-08-26 : Plays start expanded because that is
      // what it has always done; most playbooks probably only have
      // one play.  Maybe if there's multiple plays things could start
      // rolled up?
      playsExpanded: this.props.playbook.plays.map((play, idx) => this.makePlayId(play, idx))
    }
  }

  makePlayId = (play, idx) => play.play.name + '-' + idx

  render () {
    const { playbook, errorIds, taskPath, displayPath } = this.props

    const togglePlays = id => {
      const index = this.state.playsExpanded.indexOf(id)
      const newExpanded =
            index >= 0 ? [...this.state.playsExpanded.slice(0, index), ...this.state.playsExpanded.slice(index + 1, this.state.playsExpanded.length)] : [...this.state.playsExpanded, id]
      this.setState({playsExpanded: newExpanded})
    }

    // This is the header for each playbook
    let dataListCells = []
    dataListCells.push(
      <DataListCell key='name' width={1}>
        <strong>
          {playbook.phase[0].toUpperCase() + playbook.phase.slice(1)} playbook
        </strong>
      </DataListCell>)
        dataListCells.push(
        <DataListCell key='path' width={5}>
          {playbook.playbook}
        </DataListCell>)
    if (playbook.trusted) {
      dataListCells.push(
        <DataListCell key='trust'>
          <Tooltip content={<div>This playbook runs in a trusted execution context, which permits executing code on the Zuul executor and allows access to all Ansible features.</div>}>
          <Label color='blue' icon={<InfoCircleIcon />} style={{cursor: 'pointer'}}>Trusted</Label></Tooltip></DataListCell>)
    } else {
        // NOTE(ianw) : This empty cell keeps things lined up
        // correctly.  We tried a "untrusted" label but preferred
        // without.
        dataListCells.push(<DataListCell key='trust' width={1}/>)
    }

    return (
      <DataListItem isExpanded={this.state.expanded}>

        <DataListItemRow>
          <DataListToggle
            onClick={() => this.setState({expanded: !this.state.expanded})}
            isExpanded={this.state.expanded}/>
          <DataListItemCells
            dataListCells={dataListCells} />
        </DataListItemRow>

        <DataListContent isHidden={!this.state.expanded}>

          {playbook.plays.map((play, idx) => (
            <DataList isCompact={true}
                      key={this.makePlayId(play, idx)}
                      className="zuul-console-plays"
                      style={{ fontSize: 'var(--pf-global--FontSize--md)' }}>
              <DataListItem isExpanded={this.state.playsExpanded.includes(this.makePlayId(play, idx))}>
                <DataListItemRow>
                  <DataListToggle
                    onClick={() => togglePlays(this.makePlayId(play, idx))}
                    isExpanded={this.state.playsExpanded.includes(this.makePlayId(play, idx))}
                    id={this.makePlayId(play, idx)}/>
                  <DataListItemCells dataListCells={[
                                       <DataListCell key='play'>Play: {play.play.name}</DataListCell>
                                     ]}
                  />
                </DataListItemRow>
                <DataListContent
                  isHidden={!this.state.playsExpanded.includes(this.makePlayId(play, idx))}>

                  <DataList isCompact={true} style={{ fontSize: 'var(--pf-global--FontSize--md)' }} >
                    {play.tasks.map((task, idx2) => (
                      Object.entries(task.hosts).map(([hostname, host]) => (
                        <HostTask key={idx+idx2+hostname}
                          hostname={hostname}
                          taskPath={taskPath.concat([
                            idx.toString(), idx2.toString(), hostname])}
                          displayPath={displayPath} task={task} host={host}
                          errorIds={errorIds}
                          preferences={this.props.preferences}/>
                      ))))}
                  </DataList>

                </DataListContent>
              </DataListItem>
            </DataList>
          ))}

        </DataListContent>
      </DataListItem>
    )
  }
}


class Console extends React.Component {
  static propTypes = {
    errorIds: PropTypes.object,
    output: PropTypes.array,
    displayPath: PropTypes.array,
    preferences: PropTypes.object,
  }

  render () {
    const { errorIds, output, displayPath } = this.props

    return (
      <React.Fragment>
        <br />
        <span className={`zuul-console ${this.props.preferences.darkMode ? 'zuul-console-dark' : 'zuul-console-light'}`}>
          <DataList isCompact={true}
                    style={{ fontSize: 'var(--pf-global--FontSize--md)' }}>
            {
              output.map((playbook, idx) => (
                <PlayBook
                  key={idx} playbook={playbook} taskPath={[idx.toString()]}
                  displayPath={displayPath} errorIds={errorIds}
                  preferences={this.props.preferences}
                />))
            }
          </DataList>
        </span>
      </React.Fragment>
    )
  }
}

function mapStateToProps(state) {
  return {
    preferences: state.preferences,
  }
}


export default connect(mapStateToProps)(Console)
