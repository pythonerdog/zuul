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

import { TENANT_SET } from '../actions/tenant'

// undefined name means we haven't loaded anything yet; null means
// outside of tenant context.
export default (state = {name: undefined}, action) => {
  switch (action.type) {
    case TENANT_SET:
      return action.tenant
    default:
      return state
  }
}
