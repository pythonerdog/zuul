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

/*
 * NOTE(ianw) 2021-08-16
 * Some thoughts for future work:
 *
 * - Most descriptions are one line, but some a very long.
 * - Might be cool to have a fixed height and show a preview of the description
 *   that fades out, but can the be clicked to be read fully.
 * - Perhaps Zuul could format this for us, as it looks like raw RST.
 *   I think that would have to be a python/sphinx thing, can't practically
 *   do it client side.
 */

import * as React from 'react'
import PropTypes from 'prop-types'
import {
  Card,
  CardHeader,
  CardTitle,
  CardExpandableContent,
  CardBody
} from '@patternfly/react-core'

class JobDescriptionCard extends React.Component {
  static propTypes = {
    description: PropTypes.string
  }

  constructor(props) {
    super(props)

    this.state = {
      isExpanded: true
    }

    this.onExpand = () => {
      this.setState({
        isExpanded: !this.state.isExpanded
      })
    }
  }

  render() {
    if (!this.props.description) {
      return null
    }

    return (
      <React.Fragment>
        <Card className={['pf-u-m-lg']} isExpanded={this.state.isExpanded}>
          <CardHeader onExpand={ this.onExpand }>
            <CardTitle>Job description</CardTitle>
          </CardHeader>
          <CardExpandableContent>
            <CardBody style={{whiteSpace: 'pre-wrap'}}>
            {this.props.description}
            </CardBody>
          </CardExpandableContent>
        </Card>
      </React.Fragment>
    )
  }

}

export default JobDescriptionCard
