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

import PropTypes from 'prop-types'
import React from 'react'
import Select, { components } from 'react-select'
import moment from 'moment-timezone'
import { OutlinedClockIcon, ChevronDownIcon } from '@patternfly/react-icons'
import { connect } from 'react-redux'
import { setTimezoneAction } from '../../actions/timezone'

class SelectTz extends React.Component {
   static propTypes = {
     dispatch: PropTypes.func
   }

  state = {
    availableTz: moment.tz.names().map(item => ({value: item, label: item})),
    defaultValue: {value: 'UTC', label: 'UTC'}
  }

  componentDidMount () {
    this.loadState()
    window.addEventListener('storage', this.loadState)
  }

  handleChange = (selectedTz) => {
    const tz = selectedTz.value

    localStorage.setItem('zuul_tz_string', tz)
    this.updateState(tz)
  }

  loadState = () => {
    let tz = localStorage.getItem('zuul_tz_string') || ''
    if (tz) {
      this.updateState(tz)
    }
  }

  updateState = (tz) => {

    this.setState({
      currentValue: {value: tz, label: tz}
    })

    let timezoneAction = setTimezoneAction(tz)
    this.props.dispatch(timezoneAction)
  }

  render() {
    const textColor = '#fff'
    const containerStyles= {
      border: 'solid #2b2b2b',
      borderWidth: '0 0 0 1px',
      cursor: 'pointer',
      display: 'initial',
      padding: '6px'
    }
    const customStyles = {
      container: () => ({
        display: 'inline-block',
      }),
      control: () => ({
        width: 'auto',
        display: 'flex'
      }),
      singleValue: () => ({
        color: textColor,
      }),
      input: (provided) => ({
        ...provided,
        color: textColor
      }),
      dropdownIndicator:(provided) => ({
        ...provided,
        color: '#fff',
        padding: '3px',
        ':hover': {
          color: '#fff'
        }
      }),
      indicatorSeparator: () => {},
      menu: (provided) => ({
        ...provided,
        width: 'auto',
        right: '0',
        top: '22px',
      })
    }

    const DropdownIndicator = (props) => {
      return (
        <components.DropdownIndicator {...props}>
          <ChevronDownIcon />
        </components.DropdownIndicator>
      )
    }

    return (
      <div style={containerStyles}>
        <OutlinedClockIcon/>
        <Select
          className="zuul-select-tz"
          classNamePrefix="zuul-select-tz"
          styles={customStyles}
          components={{ DropdownIndicator }}
          value={this.state.currentValue}
          onChange={this.handleChange}
          options={this.state.availableTz}
          noOptionsMessage={() => 'No api found'}
          placeholder={'Select Tz'}
          defaultValue={this.state.defaultValue}
          theme={(theme) => ({
            ...theme,
            borderRadius: 0,
            spacing: {
              ...theme.spacing,
              baseUnit: 2,
            },
          })}
        />
      </div>
    )
  }
}

export default connect()(SelectTz)
