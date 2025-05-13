// Copyright 2021 Acme Gating, LLC
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

// This is an abbreviated rendering of the app which only renders the
// AuthProvider.  This is rendered in a hidden iframe during
// authentication token renewal.  We don't need to render the entire
// app, and we also don't need to render the AuthProvider with all of
// our settings.

import React from 'react'
import { AuthProvider } from 'oidc-react'
import { UserManager } from 'oidc-client'

class SilentCallback extends React.Component {
  render() {
    const oidcConfig = {
      autoSignIn: false,
      userManager: new UserManager(),
    }

    return <AuthProvider {...oidcConfig}/>
  }
}

export default SilentCallback
