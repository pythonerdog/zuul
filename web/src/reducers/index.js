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

import { combineReducers } from 'redux'

import auth from './auth'
import autoholds from './autoholds'
import change from './change'
import component from './component'
import flavors from './flavors'
import freezejob from './freezejob'
import notifications from './notifications'
import build from './build'
import images from './images'
import info from './info'
import job from './job'
import jobgraph from './jobgraph'
import jobs from './jobs'
import labels from './labels'
import logfile from './logfile'
import nodesetRequests from './nodesetRequests'
import nodes from './nodes'
import openapi from './openapi'
import project from './project'
import pipelines from './pipelines'
import projects from './projects'
import preferences from './preferences'
import providers from './providers'
import semaphores from './semaphores'
import status from './status'
import statusExpansion from './statusExpansion'
import tenant from './tenant'
import tenants from './tenants'
import tenantStatus from './tenantStatus'
import timezone from './timezone'
import user from './user'

const reducers = {
  auth,
  autoholds,
  build,
  change,
  component,
  tenantStatus,
  flavors,
  freezejob,
  notifications,
  images,
  info,
  job,
  jobgraph,
  jobs,
  labels,
  logfile,
  nodesetRequests,
  nodes,
  openapi,
  pipelines,
  project,
  projects,
  providers,
  semaphores,
  status,
  statusExpansion,
  tenant,
  tenants,
  timezone,
  preferences,
  user,
}

export default combineReducers(reducers)
