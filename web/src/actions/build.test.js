// Copyright 2019 Red Hat, Inc
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

import * as buildAction from './build'

it('processes job-output properly', () => {
  expect(buildAction.didTaskFail({failed: true})).toEqual(true)

  expect(buildAction.hasInterestingKeys({rc: 42}, ['rc'])).toEqual(true)
  expect(buildAction.hasInterestingKeys({noop: 42}, ['rc'])).toEqual(false)

  // Check trailing / are removed
  let obj = {children: [], mimetype: 'test', name: 'test'}
  let tree = buildAction.renderTree(
    {linkPrefix: 'test/'},
    {log_url: 'http://test/', uuid: 'test'},
    '/', obj, (a) => (a), (a) => (a))
  expect(tree).toEqual(
    {'icon': 'fa fa-file-o', 'nodes': [], 'text': 'http://test'})
})

it('processes filename with % properly', () => {
  let obj = {children: [], mimetype: 'test', name: 'test%el'}
  let tree = buildAction.renderTree(
    {linkPrefix: 'test/'},
    {log_url: 'http://test/', uuid: 'test'},
    '/', obj, (a) => (a), (_log_url, path, name) => (path + name))
  expect(tree).toEqual(
    {'icon': 'fa fa-file-o', 'nodes': [], 'text': '/test%25el'})
})
