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

import React from 'react'
import ReactDOM from 'react-dom'
import { Provider } from 'react-redux'
import configureStore from '../../store'
import BuildOutput from './BuildOutput'

const fakeOutput = (width, height) => ({
  test: {
    failed: [
      {
        zuul_log_id: 'fake',
        stderr_lines: Array(height).fill('x'.repeat(width))
      },
    ],
  },
})

it('BuildOutput renders big task', () => {
  const div = document.createElement('div')
  const output = fakeOutput(512, 1024)
  const begin = performance.now()
  const store = configureStore()
  ReactDOM.render(
    <Provider store={store}>
    <BuildOutput output={output} />
    </Provider>, div, () => {
    const end = performance.now()
    console.log('Render took ' + (end - begin) + ' milliseconds.')
  })
})
