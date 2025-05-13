// Copyright 2024 BMW Group
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

import {
  calculateQueueItemTimes,
  ChangeLink,
  getRefs
} from './Misc'

import QueueItemProgress from './QueueItemProgress'

function QueueItemPopover({ item, triggerElement }) {
  // TODO (felix): Move the triggerElement to be used as children
  // instead. This should make the usage of the QueueItemPopover
  // a little nicer.

  const [isVisible, setIsVisible] = useState(null)
  const times = calculateQueueItemTimes(item)

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
      shouldClose={() => {setIsVisible(null)}}
      headerContent={
        getRefs(item).map((change, idx) => (
          <div key={idx}>
            {change.project} <ChangeLink change={change} />
          </div>
        ))
      }
      bodyContent={
        <QueueItemProgress item={item} times={times} />
      }
    >
    {
      // The triggerElement must be placed within the Popover to open it

      // The event handlers below implement a "scrubbing" behavior.
      // As long as a button is depressed while entering or leaving
      // the square, we will set the element to be controlled and
      // force it to be shown (when entering) or not (when leaving).
      // This leaves each of the squares in a controlled state, but if
      // the user re-enters a previously controlled square in the off
      // state without clicking, we will reset the element to be
      // uncontrolled, and a subsequent click will toggle it on.
    }
      <span
        onMouseEnter={(e) => {
          if (e.buttons) { setIsVisible(true) }
          else { setIsVisible(null) }
        }}
        onMouseLeave={(e) => {
          if (e.buttons) { setIsVisible(false) }
          else { setIsVisible(null) }
        }}
      >
        {triggerElement}
      </span>
    </Popover>
  )
}

QueueItemPopover.propTypes = {
  item: PropTypes.object,
  triggerElement: PropTypes.object,
}

function mapStateToProps(state) {
  return {
    darkMode: state.preferences.darkMode,
  }
}

export default connect(mapStateToProps)(QueueItemPopover)
