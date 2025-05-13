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

import { applyMiddleware, compose, createStore } from 'redux'
import appReducer from './reducers'
import reduxImmutableStateInvariant from 'redux-immutable-state-invariant'
import thunk from 'redux-thunk'

export default function configureStore(initialState) {
  // Add support for Redux devtools
  const composeEnhancers =
    window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose
  return createStore(
    appReducer,
    initialState,
    // Warn us if we accidentially mutate state directly in the Redux store
    // (only during development).
    composeEnhancers(
      applyMiddleware(
        thunk,
        // TODO (felix): Re-enable the status.status path once we know how to
        // solve the weird state mutations that are done somewhere deep within
        // the logic of the status page (or its child components).
        reduxImmutableStateInvariant({
          ignore: [
            'status.status',
          ]
        })
      )
    )
  )
}
