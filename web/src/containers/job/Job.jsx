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

import * as React from 'react'
import PropTypes from 'prop-types'
import {
  Tab,
  Tabs,
  TabTitleText,
  Title
} from '@patternfly/react-core'

import JobVariant from './JobVariant'

class Job extends React.Component {
  static propTypes = {
    job: PropTypes.array.isRequired,
  }

  state = {
    activeTabeKey: 0
  }

  renderVariantTitle (variant) {
    let title = variant.variant_description
    if (!title) {
      title = ''
      /* NOTE(ianw) 2021-08-13 : it seems like if this is only defined
         for one branch we don't get the branches.  This might be a
         bug.  In this case, use the source context branch (i.e. where
         it's defined */
      if (variant.branches === null || variant.branches.length === 0) {
        title = variant.source_context.branch
      } else {
        variant.branches.forEach((item) => {
          if (title) {
            title += ', '
          }
          title += item
        })
      }
    }
    return title
  }

  handleTabClick ( tabIndex ) {
    this.setState({
      activeTabKey: tabIndex
    })
  }

  render () {
    const { job } = this.props
    const { activeTabKey } = this.state

    return (
      <React.Fragment>
        <Title headingLevel="h2">
          Details for job <span style={{color: 'var(--pf-global--primary-color--100)'}}>{job[0].name}</span>
        </Title>
        <Tabs activeKey={activeTabKey}
              onSelect={(event, tabIndex) => this.handleTabClick(tabIndex)}
              isBox>
          {job.map((variant, idx) => (
            <Tab eventKey={idx} key={idx}
                 title={<TabTitleText>{this.renderVariantTitle(variant)}</TabTitleText>}>
              <JobVariant
                variant={job[idx]}
                parent={this}
              />
            </Tab>
          ))}
        </Tabs>
      </React.Fragment>
    )
  }
}

export default Job
