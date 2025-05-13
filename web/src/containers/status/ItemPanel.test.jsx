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

import React from 'react'
import { Link, BrowserRouter as Router } from 'react-router-dom'
import { Provider } from 'react-redux'
import { create } from 'react-test-renderer'
import { Button } from '@patternfly/react-core'

import { setTenantAction } from '../../actions/tenant'
import configureStore from '../../store'
import ItemPanel from './ItemPanel'


const fakeItem = {
  refs: [{
    project: 'org-project'
  }],
  jobs: [{
    name: 'job-name',
    url: 'stream/42',
    result: null
  }]
}

it('item panel render multi tenant links', () => {
  const store = configureStore()
  store.dispatch(setTenantAction('tenant-one', false))
  const application = create(
      <Provider store={store}>
        <Router>
          <ItemPanel item={fakeItem} globalExpanded={true} />
        </Router>
      </Provider>
    )
  const jobLink = application.root.findByType(Link)
  expect(jobLink.props.to).toEqual(
    '/t/tenant-one/stream/42')
  const skipButton = application.root.findAllByType(Button)
  expect(skipButton === undefined)
})

it('item panel render white-label tenant links', () => {
  const store = configureStore()
  store.dispatch(setTenantAction('tenant-one', true))
  const application = create(
    <Provider store={store}>
      <Router>
        <ItemPanel item={fakeItem} globalExpanded={true} />
      </Router>
    </Provider>
  )
  const jobLink = application.root.findByType(Link)
  expect(jobLink.props.to).toEqual(
    '/stream/42')
  const skipButton = application.root.findAllByType(Button)
  expect(skipButton === undefined)
})

it('item panel skip jobs', () => {
  const fakeItem = {
    refs: [{
      project: 'org-project'
    }],
    jobs: [{
      name: 'job-name',
      url: 'stream/42',
      result: 'skipped'
    }]
  }

  const store = configureStore()
  store.dispatch(setTenantAction('tenant-one', true))
  const application = create(
    <Provider store={store}>
      <Router>
        <ItemPanel item={fakeItem} globalExpanded={true} />
      </Router>
    </Provider>
  )
  const skipButton = application.root.findByType(Button)
  expect(skipButton.props.children.includes('skipped job'))
})

/* Backwards compat; remove after circular dependency refactor */

const fakeChange = {
  project: 'org-project',
  jobs: [{
    name: 'job-name',
    url: 'stream/42',
    result: null
  }]
}

it('item panel backwards compat render multi tenant links', () => {
  const store = configureStore()
  store.dispatch(setTenantAction('tenant-one', false))
  const application = create(
      <Provider store={store}>
        <Router>
          <ItemPanel item={fakeChange} globalExpanded={true} />
        </Router>
      </Provider>
    )
  const jobLink = application.root.findByType(Link)
  expect(jobLink.props.to).toEqual(
    '/t/tenant-one/stream/42')
  const skipButton = application.root.findAllByType(Button)
  expect(skipButton === undefined)
})

it('item panel backwards compat render white-label tenant links', () => {
  const store = configureStore()
  store.dispatch(setTenantAction('tenant-one', true))
  const application = create(
    <Provider store={store}>
      <Router>
        <ItemPanel item={fakeChange} globalExpanded={true} />
      </Router>
    </Provider>
  )
  const jobLink = application.root.findByType(Link)
  expect(jobLink.props.to).toEqual(
    '/stream/42')
  const skipButton = application.root.findAllByType(Button)
  expect(skipButton === undefined)
})

it('item panel backwards compat skip jobs', () => {
  const fakeChange = {
    project: 'org-project',
    jobs: [{
      name: 'job-name',
      url: 'stream/42',
      result: 'skipped'
    }]
  }

  const store = configureStore()
  store.dispatch(setTenantAction('tenant-one', true))
  const application = create(
    <Provider store={store}>
      <Router>
        <ItemPanel item={fakeChange} globalExpanded={true} />
      </Router>
    </Provider>
  )
  const skipButton = application.root.findByType(Button)
  expect(skipButton.props.children.includes('skipped job'))
})
