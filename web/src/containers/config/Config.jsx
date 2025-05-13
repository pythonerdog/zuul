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
import { connect } from 'react-redux'
import {
  Button,
  ButtonVariant,
  Modal,
  ModalVariant,
  Switch,
  Select,
  SelectOption,
  SelectVariant
} from '@patternfly/react-core'
import { CogIcon } from '@patternfly/react-icons'
import { setPreference } from '../../actions/preferences'
import { resolveDarkMode, setDarkMode } from '../../Misc'

class ConfigModal extends React.Component {

  static propTypes = {
    location: PropTypes.object,
    tenant: PropTypes.object,
    preferences: PropTypes.object,
    timezone: PropTypes.string,
    remoteData: PropTypes.object,
    dispatch: PropTypes.func
  }

  constructor(props) {
    super(props)
    this.state = {
      isModalOpen: false,
      autoReload: false,
      theme: 'Auto',
      isThemeOpen: false,
    }
    this.handleModalToggle = () => {
      this.setState(({ isModalOpen }) => ({
        isModalOpen: !isModalOpen
      }))
      this.resetState()
    }

    this.handleEscape = () => {
      if (this.state.isThemeOpen) {
        this.setState(({ isThemeOpen }) => ({
          isThemeOpen: !isThemeOpen,
        }))
      } else {
        this.handleModalToggle()
      }
    }

    this.handleThemeToggle = () => {
      this.setState(({ isThemeOpen }) => ({
        isThemeOpen: !isThemeOpen,
      }))
    }

    this.handleThemeSelect = (event, selection) => {
      this.setState({
        theme: selection,
        isThemeOpen: false
      })
    }

    this.handleTheme = () => {
      let darkMode = resolveDarkMode(this.state.theme)
      setDarkMode(darkMode)
    }

    this.handleSave = () => {
      this.handleModalToggle()
      this.props.dispatch(setPreference('autoReload', this.state.autoReload))
      this.props.dispatch(setPreference('theme', this.state.theme))
      this.handleTheme()
    }

    this.handleAutoReload = () => {
      this.setState(({ autoReload }) => ({
        autoReload: !autoReload
      }))
    }
  }

  resetState() {
    this.setState({
      autoReload: this.props.preferences.autoReload,
      theme: this.props.preferences.theme,
    })
  }

  render() {
    const { isModalOpen, autoReload, theme, isThemeOpen } = this.state
    return (
      <React.Fragment>
        <Button
          variant={ButtonVariant.plain}
          key="cog"
          onClick={this.handleModalToggle}>
          <CogIcon />
        </Button>
        <Modal
          variant={ModalVariant.small}
          title="Preferences"
          isOpen={isModalOpen}
          onClose={this.handleModalToggle}
          onEscapePress={this.handleEscape}
          actions={[
            <Button key="confirm" variant="primary" onClick={this.handleSave}>
              Confirm
            </Button>,
            <Button key="cancel" variant="link" onClick={this.handleModalToggle}>
              Cancel
            </Button>
          ]}
        >
          <div>
            <p key="info">Application settings are saved in browser local storage only. They are applied whether authenticated or not.</p>
          </div>
          <div>
            <Switch
              key="autoreload"
              id="autoreload"
              label="Auto reload status page"
              isChecked={autoReload}
              onChange={this.handleAutoReload}
            />
          </div>
          <div style={{'paddingTop': '25px'}}>
            <p key="theme-info">Select your preferred theme, auto will base it on your system preference.</p>
          </div>
          <div>
            <Select
              variant={SelectVariant.single}
              label="Select Input"
              onToggle={this.handleThemeToggle}
              onSelect={this.handleThemeSelect}
              selections={theme}
              isOpen={isThemeOpen}
              menuAppendTo="parent"
            >
              <SelectOption key="auto" value="Auto"/>
              <SelectOption key="light" value="Light"/>
              <SelectOption key="dark" value="Dark"/>
            </Select>
          </div>
        </Modal>
      </React.Fragment>
    )
  }
}

export default connect(state => ({
  preferences: state.preferences,
}))(ConfigModal)
