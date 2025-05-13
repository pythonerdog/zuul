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

import React from 'react'
import { create, act } from 'react-test-renderer'
import ReactDOM from 'react-dom'
import { Link, BrowserRouter as Router } from 'react-router-dom'
import { Provider } from 'react-redux'
import { BroadcastChannel, createLeaderElection } from 'broadcast-channel'

import { fetchInfoIfNeeded } from './actions/info'
import configureStore from './store'
import App from './App'
import TenantsPage from './pages/Tenants'
import StatusPage from './pages/Status'
import ZuulAuthProvider from './ZuulAuthProvider'
import * as api from './api'

api.fetchInfo = jest.fn()
api.fetchTenants = jest.fn()
api.fetchStatus = jest.fn()
api.fetchConfigErrors = jest.fn()
api.fetchConfigErrors.mockImplementation(() => Promise.resolve({data: []}))

it('renders without crashing', async () => {
  const store = configureStore()
  const channel = new BroadcastChannel('zuul')
  const auth_election = createLeaderElection(channel)
  const div = document.createElement('div')
  ReactDOM.render(
    <Provider store={store}>
      <ZuulAuthProvider channel={channel} election={auth_election}>
        <Router><App /></Router>
      </ZuulAuthProvider>
    </Provider>,
    div)
  ReactDOM.unmountComponentAtNode(div)
  await auth_election.die()
  await channel.close()
})

it('renders multi tenant', async () => {
  const store = configureStore()
  const channel = new BroadcastChannel('zuul')
  const auth_election = createLeaderElection(channel)
  api.fetchInfo.mockImplementation(
    () => Promise.resolve({data: {
      info: {
        capabilities: {
          auth: {
            realms: {},
            default_realm: null,
          },
        },
      }}})
  )
  api.fetchTenants.mockImplementation(
    () => Promise.resolve({data: [{name: 'openstack'}]})
  )

  const application = create(
    <Provider store={store}>
      <ZuulAuthProvider channel={channel} election={auth_election}>
        <Router><App /></Router>
      </ZuulAuthProvider>
    </Provider>
  )

  await act(async () => {
    await store.dispatch(fetchInfoIfNeeded())
  })

  // Link should be tenant scoped
  const topMenuLinks = application.root.findAllByType(Link)
  expect(topMenuLinks[0].props.to).toEqual('/')
  expect(topMenuLinks[1].props.to).toEqual('/components')
  expect(topMenuLinks[2].props.to).toEqual('/openapi')
  expect(topMenuLinks[3].props.to).toEqual('/t/openstack/status')
  expect(topMenuLinks[4].props.to).toEqual('/t/openstack/projects')
  // Location should be /tenants
  expect(location.pathname).toEqual('/tenants')
  // Info should tell multi tenants
  expect(store.getState().info.tenant).toEqual(undefined)
  // Tenants list has been rendered
  expect(application.root.findAllByType(TenantsPage)).not.toEqual(null)
  // Fetch tenants has been called
  expect(api.fetchTenants).toBeCalled()
  await auth_election.die()
  await channel.close()
})

it('renders single tenant', async () => {
  const store = configureStore()
  const channel = new BroadcastChannel('zuul')
  const auth_election = createLeaderElection(channel)
  api.fetchInfo.mockImplementation(
    () => Promise.resolve({data: {
      info: {
        capabilities: {
          auth: {
            realms: {},
            default_realm: null,
          },
        },
        tenant: 'openstack'}
    }})
  )
  api.fetchStatus.mockImplementation(
    () => Promise.resolve({data: {pipelines: []}})
  )

  const application = create(
    <Provider store={store}>
      <ZuulAuthProvider channel={channel} election={auth_election}>
        <Router><App /></Router>
      </ZuulAuthProvider>
    </Provider>
  )

  await act(async () => {
    await store.dispatch(fetchInfoIfNeeded())
  })

  // Link should be white-label scoped
  const topMenuLinks = application.root.findAllByType(Link)
  expect(topMenuLinks[0].props.to).toEqual('/status')
  expect(topMenuLinks[1].props.to).toEqual('/openapi')
  expect(topMenuLinks[2].props.to.pathname).toEqual('/status')
  expect(topMenuLinks[3].props.to.pathname).toEqual('/projects')
  // Location should be /status
  expect(location.pathname).toEqual('/status')
  // Info should tell white label tenant openstack
  expect(store.getState().info.tenant).toEqual('openstack')
  // Status page has been rendered
  expect(application.root.findAllByType(StatusPage)).not.toEqual(null)
  // Fetch status has been called
  expect(api.fetchStatus).toBeCalled()
  await auth_election.die()
  await channel.close()
})
