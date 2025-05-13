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
import * as moment from 'moment'
import { ExternalLinkAltIcon } from '@patternfly/react-icons'

function removeHash() {
  // Remove location hash from url
  window.history.pushState('', document.title, window.location.pathname)
}

function ExternalLink(props) {
  const { target } = props

  return (
    <a href={target}>
      <span>
        {props.children}
        {/* As we want the icon to be smaller than "sm", we have to specify the
            font-size directly */}
        <ExternalLinkAltIcon
          style={{
            marginLeft: 'var(--pf-global--spacer--xs)',
            color: 'var(--pf-global--Color--400)',
            fontSize: 'var(--pf-global--icon--FontSize--sm)',
            verticalAlign: 'super',
          }}
        />
      </span>
    </a>
  )
}

ExternalLink.propTypes = {
  target: PropTypes.string,
  children: PropTypes.node,
}

function buildExternalLink(ref) {
  /* TODO (felix): What should we show for periodic builds
      here? They don't provide a change, but the ref_url is
      also not usable */
  if (ref.ref_url && ref.change) {
    return (
      <ExternalLink target={ref.ref_url}>
        <strong>Change </strong>
        {ref.change},{ref.patchset}
      </ExternalLink>
    )
  } else if (ref.ref_url && ref.newrev) {
    return (
      <ExternalLink target={ref.ref_url}>
        <strong>Revision </strong>
        {ref.newrev.slice(0, 7)}
      </ExternalLink>
    )
  }

  return null
}

function buildExternalTableLink(ref) {
  /* TODO (felix): What should we show for periodic builds
      here? They don't provide a change, but the ref_url is
      also not usable */
  if (ref.ref_url && ref.change) {
    return (
      <ExternalLink target={ref.ref_url}>
        {ref.change},{ref.patchset}
      </ExternalLink>
    )
  } else if (ref.ref_url && ref.newrev) {
    return (
      <ExternalLink target={ref.ref_url}>
        {ref.newrev.slice(0, 7)}
      </ExternalLink>
    )
  }

  return null
}

function describeRef(ref) {
  if (ref.change) {
    return `Change ${ref.change}`
  } else {
    return `Ref ${ref.ref}`
  }
}

function renderRefInfo(ref) {
  const refinfo = ref.branch ? (
    <>
      <strong>Branch </strong> {ref.branch}
    </>
  ) : (
    <>
      <strong>Ref </strong> {ref.ref}
    </>
  )
  const oldrev = ref.oldrev ? (
    <><br /><strong>Old</strong> {ref.oldrev}</>
  ) : (<></>)
  const newrev = ref.newrev ? (
    <><br /><strong>New</strong> {ref.newrev}</>
  ) : (<></>)

  return (
    <>
      {refinfo}
      {oldrev}
      {newrev}
    </>
  )
}

function IconProperty(props) {
  const { icon, value, WrapElement = 'span' } = props
  return (
    <WrapElement style={{ marginLeft: '25px' }}>
      <span
        style={{
          marginRight: 'var(--pf-global--spacer--sm)',
          marginLeft: '-25px',
        }}
      >
        {icon}
      </span>
      <span>{value}</span>
    </WrapElement>
  )
}

IconProperty.propTypes = {
  icon: PropTypes.node,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.node]),
  WrapElement: PropTypes.func,
}

// https://github.com/kitze/conditional-wrap
// appears to be the first implementation of this pattern
const ConditionalWrapper = ({ condition, wrapper, children }) =>
  condition ? wrapper(children) : children

function resolveDarkMode(theme) {
  let darkMode = false

  if (theme === 'Auto') {
    let matchMedia = window.matchMedia || function () {
      return {
        matches: false,
      }
    }

    darkMode = matchMedia('(prefers-color-scheme: dark)').matches
  } else if (theme === 'Dark') {
    darkMode = true
  }

  return darkMode
}

function setDarkMode(darkMode) {
  if (darkMode) {
    document.documentElement.classList.add('pf-theme-dark')
  } else {
    document.documentElement.classList.remove('pf-theme-dark')
  }
}

function formatTime(ms) {
  return moment.duration(ms).format({
    template: 'h [hr] m [min]',
    largest: 2,
    minValue: 1,
    usePlural: false,
  })
}

export {
  buildExternalLink,
  buildExternalTableLink,
  ConditionalWrapper,
  describeRef,
  ExternalLink,
  formatTime,
  IconProperty,
  removeHash,
  renderRefInfo,
  resolveDarkMode,
  setDarkMode,
}
