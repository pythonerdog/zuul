// Copyright 2024 BMW Group
// Copyright 2025 Acme Gating, LLC
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

import React, { useState } from 'react'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import {
  Popover,
} from '@patternfly/react-core'

import { formatProviderName } from '../../Misc'

function NodePopover({ node, triggerElement }) {
  // TODO (felix): Move the triggerElement to be used as children
  // instead. This should make the usage of the QueueItemPopover
  // a little nicer.

  const [isVisible, setIsVisible] = useState(null)
  const [isPinned, setIsPinned] = useState(false)

  return (
    <Popover
      className="zuul-queue-item-popover"
      aria-label="QueueItem Popover"
      isVisible={isVisible}
      // This custom close handler is only invoked if isVisible is
      // non-null (i.e., we are scrubbing).  It is most likely
      // happening on a release at the end of a scrub, so set the
      // element back to uncontrolled mode and leave the last visible
      // state.  The user can click or hit escape to close the popup
      // if they want.
      shouldClose={() => {setIsVisible(null); setIsPinned(false)}}
      headerContent={
          <div>
            {node.label}
          </div>
      }
      bodyContent={
        <>
          <div>State: {node.state}</div>
          <div>Provider: {formatProviderName(node.provider)}</div>
        </>
      }
    >
    {
      // The triggerElement must be placed within the Popover to open it

      // This behavior isn't exactly what we want -- we want to be
      // able to move the mouse into the popover without it
      // disappearing, but that isn't easily possible with the current
      // version of patternfly-react.  Later versions of
      // patternfly-react improve this.  For now, this sets up a
      // system where if you click/tap twice on the square, the
      // popover will stay up.
    }
      <span
        onMouseEnter={() => {
          setIsVisible(true)
          setIsPinned(false)
        }}
        onMouseDown={() => {
          if (isVisible === null)
            setIsPinned(true)
          else
            setIsPinned(!isPinned)
        }}
        onMouseLeave={() => {
          if(!isPinned) {
            setIsVisible(false)
            setIsPinned(false)
          }
        }}
      >
        {triggerElement}
      </span>
    </Popover>
  )
}

NodePopover.propTypes = {
  node: PropTypes.object,
  triggerElement: PropTypes.object,
}

function mapStateToProps(state) {
  return {
    darkMode: state.preferences.darkMode,
  }
}

export default connect(mapStateToProps)(NodePopover)
