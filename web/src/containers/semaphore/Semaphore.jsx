// Copyright 2018 Red Hat, Inc
// Copyright 2022 Acme Gating, LLC
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
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import { Link } from 'react-router-dom'
import {
  DescriptionList,
  DescriptionListTerm,
  DescriptionListGroup,
  DescriptionListDescription,
  Spinner,
} from '@patternfly/react-core'

function Semaphore({ semaphore, tenant, fetching }) {
  if (fetching && !semaphore) {
    return (
      <center>
        <Spinner size="xl" />
      </center>
    )
  }
  if (!semaphore) {
    return (
      <div>
        No semaphore found
      </div>
    )
  }
  const rows = []
  rows.push({label: 'Name', value: semaphore.name})
  rows.push({label: 'Current Holders', value: semaphore.holders.count})
  rows.push({label: 'Max', value: semaphore.max})
  rows.push({label: 'Global', value: semaphore.global ? 'Yes' : 'No'})
  if (semaphore.global) {
    rows.push({label: 'Holders in Other Tenants',
               value: semaphore.holders.other_tenants})
  }
  semaphore.holders.this_tenant.forEach(holder => {
    rows.push({label: 'Held By',
               value: <Link to={`${tenant.linkPrefix}/buildset/${holder.buildset_uuid}`}>
                        {holder.job_name}
                      </Link>})
  })
  return (
    <DescriptionList isHorizontal
                     style={{'--pf-c-description-list--RowGap': '0.5rem'}}
                     className='pf-u-m-xl'>
      {rows.map((item, idx) => (
        <DescriptionListGroup key={idx}>
          <DescriptionListTerm>
            {item.label}
          </DescriptionListTerm>
          <DescriptionListDescription>
            {item.value}
          </DescriptionListDescription>
        </DescriptionListGroup>
      ))}
    </DescriptionList>
  )
}

Semaphore.propTypes = {
  semaphore: PropTypes.object.isRequired,
  fetching: PropTypes.bool.isRequired,
  tenant: PropTypes.object.isRequired,
}

function mapStateToProps(state) {
  return {
    tenant: state.tenant,
  }
}

export default connect(mapStateToProps)(Semaphore)
