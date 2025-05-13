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

import React, { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import {
  Breadcrumb,
  BreadcrumbItem,
  Divider,
  EmptyState,
  EmptyStateVariant,
  EmptyStateIcon,
  Title,
  ToggleGroup,
  ToggleGroupItem,
} from '@patternfly/react-core'
import { FileCodeIcon } from '@patternfly/react-icons'

import { Fetching } from '../Fetching'

// Helper function to sort list of numbers in ascending order
const sortNumeric = (a, b) => a - b

// When scrolling down to a highlighted section, we don't want to want to keep a little bit of
// context.
const SCROLL_OFFSET = -50

export default function LogFile({
  logfileName,
  logfileContent,
  isFetching,
  handleBreadcrumbItemClick,
  location,
  history,
  ...props
}) {
  const [severity, setSeverity] = useState(props.severity)
  const [highlightStart, setHighlightStart] = useState(0)
  const [highlightEnd, setHighlightEnd] = useState(0)
  // We only want to scroll down to the highlighted section if the highlight
  // fields we're populated from the URL parameters. Here we assume that we
  // always want to scroll when the page is loaded and therefore disable the
  // initialScroll parameter in the onClick handler that is called when a line
  // or section is marked.
  const [scrollOnPageLoad, setScrollOnPageLoad] = useState(true)

  useEffect(() => {
    // Only highlight the lines if the log is present (otherwise it doesn't make
    // sense). Although, scrolling to the selected section only works once the
    // necessary log lines are part of the DOM tree.
    // Additionally note that if we set highlightStart before the page content
    // is available then the window scrolling won't match any lines and we won't
    // scroll. Then when we try to set highlightStart after page content is loaded
    // the value isn't different than what is set previously preventing the
    // scroll event from firing.
    if (!isFetching) {
      // Get the line numbers to highlight from the URL and directly cast them to
      // a number. The substring(1) removes the '#' character.
      const lines = location.hash
        .substring(1)
        .split('-')
        .map(Number)
        .sort(sortNumeric)
      if (lines.length > 1) {
        setHighlightStart(lines[0])
        setHighlightEnd(lines[1])
      } else if (lines.length === 1) {
        setHighlightStart(lines[0])
        setHighlightEnd(lines[0])
      }
    }
  }, [location.hash, isFetching])

  useEffect(() => {
    const scrollToHighlightedLine = () => {
      const elements = document.getElementsByClassName('ln-' + highlightStart)
      if (elements.length > 0) {
        // When scrolling down to the highlighted section keep some vertical
        // offset so we can see some contextual log lines.
        const y =
          elements[0].getBoundingClientRect().top +
          window.pageYOffset +
          SCROLL_OFFSET
        window.scrollTo({ top: y, behavior: 'smooth' })
      }
    }

    if (scrollOnPageLoad) {
      scrollToHighlightedLine()
    }
  }, [scrollOnPageLoad, highlightStart])

  function handleItemClick(isSelected, event) {
    const id = parseInt(event.currentTarget.id)
    setSeverity(id)
    writeSeverityToUrl(id)
    // TODO (felix): Should we add a state for the toggling "progress", so we
    // can show a spinner (like fetching) when the new log level lines are
    // "calculated". As this might take some time, the UI is often unresponsive
    // when clicking on a log level button.
  }

  function writeSeverityToUrl(severity) {
    const urlParams = new URLSearchParams('')
    urlParams.append('severity', severity)
    history.push({
      pathname: location.pathname,
      search: urlParams.toString(),
    })
  }

  function updateSelection(event) {
    const lines = window.location.hash.substring(1).split('-').map(Number)
    const lineClicked = Number(event.currentTarget.innerText)
    if (!event.shiftKey || lines.length === 0) {
      // First line clicked
      lines[0] = [lineClicked]
      lines.splice(1, 1)
    } else {
      // Second line shift-clicked
      const distances = lines.map((pos) => Math.abs(lineClicked - pos))
      // Adjust the range based on the edge distance
      if (distances[0] < distances[1]) {
        lines[0] = lineClicked
      } else {
        lines[1] = lineClicked
      }
    }
    window.location.hash = '#' + lines.sort(sortNumeric).join('-')
    // We don't want to scroll to that section if we just highlighted the lines
    setScrollOnPageLoad(false)
  }

  function renderLogfile(logfileContent, severity) {
    return (
      <>
        <ToggleGroup aria-label="Log line severity filter">
          <ToggleGroupItem
            buttonId='0'
            text='All'
            isSelected={severity === 0}
            onChange={handleItemClick}
          />
          <ToggleGroupItem
            buttonId='1'
            text='Debug'
            isSelected={severity === 1}
            onChange={handleItemClick}
          />
          <ToggleGroupItem
            buttonId='2'
            text='Info'
            isSelected={severity === 2}
            onChange={handleItemClick}
          />
          <ToggleGroupItem
            buttonId='3'
            text='Warning'
            isSelected={severity === 3}
            onChange={handleItemClick}
          />
          <ToggleGroupItem
            buttonId='4'
            text='Error'
            isSelected={severity === 4}
            onChange={handleItemClick}
          />
          <ToggleGroupItem
            buttonId='5'
            text='Trace'
            isSelected={severity === 5}
            onChange={handleItemClick}
          />
          <ToggleGroupItem
            buttonId='6'
            text='Audit'
            isSelected={severity === 6}
            onChange={handleItemClick}
          />
          <ToggleGroupItem
            buttonId='7'
            text='Critical'
            isSelected={severity === 7}
            onChange={handleItemClick}
          />
        </ToggleGroup>
        <Divider />
        <pre className="zuul-log-output">
          <table>
            <tbody>
              {logfileContent.map((line) => {
                // Highlight the line if it's part of the selected range
                const highlightLine =
                  line.index >= highlightStart && line.index <= highlightEnd
                return (
                  line.severity >= severity && (
                    <tr
                      key={line.index}
                      className={`ln-${line.index} ${
                        highlightLine ? 'highlight' : ''
                      }`}
                    >
                      <td className="line-number" onClick={updateSelection}>
                        {line.index}
                      </td>
                      <td>
                        <span
                          className={`log-message zuul-log-sev-${
                            line.severity || 0
                          }`}
                        >
                          {line.text + '\n'}
                        </span>
                      </td>
                    </tr>
                  )
                )
              })}
            </tbody>
          </table>
        </pre>
      </>
    )
  }

  // Split the logfile's name to show some breadcrumbs
  const logfilePath = logfileName.split('/')

  const content =
    !logfileContent && isFetching ? (
      <Fetching />
    ) : logfileContent ? (
      renderLogfile(logfileContent, severity)
    ) : (
      <EmptyState variant={EmptyStateVariant.small}>
        <EmptyStateIcon icon={FileCodeIcon} />
        <Title headingLevel="h4" size="lg">
          This logfile could not be found
        </Title>
      </EmptyState>
    )

  return (
    <>
      <div style={{ padding: '1rem' }}>
        <Breadcrumb>
          <BreadcrumbItem
            key={-1}
            // Fake a link via the "to" property to get an appropriate CSS
            // styling for the breadcrumb. The link itself is handled via a
            // custom onClick handler to allow client-side routing with
            // react-router. The BreadcrumbItem only allows us to specify a
            // <a href=""> as link which would post-back to the server.
            to="#"
            onClick={() => handleBreadcrumbItemClick()}
          >
            Logs
          </BreadcrumbItem>
          {logfilePath.map((part, index) => (
            <BreadcrumbItem
              key={index}
              isActive={index === logfilePath.length - 1}
            >
              {part}
            </BreadcrumbItem>
          ))}
        </Breadcrumb>
      </div>
      {content}
    </>
  )
}

LogFile.propTypes = {
  logfileName: PropTypes.string.isRequired,
  logfileContent: PropTypes.array,
  severity: PropTypes.number,
  isFetching: PropTypes.bool.isRequired,
  handleBreadcrumbItemClick: PropTypes.func.isRequired,
  location: PropTypes.object.isRequired,
  history: PropTypes.object.isRequired,
}

LogFile.defaultProps = {
  severity: 0,
}
