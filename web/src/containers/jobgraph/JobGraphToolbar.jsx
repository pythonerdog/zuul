// Copyright 2020 BMW Group
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

import React, { useState } from 'react'
import PropTypes from 'prop-types'
import {
  Button,
  TextInput,
  Dropdown,
  DropdownItem,
  DropdownPosition,
  DropdownToggle,
  Toolbar,
  ToolbarContent,
  ToolbarGroup,
  ToolbarItem,
  ToolbarToggleGroup,
} from '@patternfly/react-core'


function JobGraphToolbar(props) {
  const pipelineSet = new Set()
  props.project.configs.forEach((config) => {
    config.pipelines.forEach((pipeline) => {
      pipelineSet.add(pipeline.name)
    })
  })
  const pipelines = Array.from(pipelineSet)

  const [isPipelineOpen, setIsPipelineOpen] = useState(false)
  const [currentPipeline, setCurrentPipeline] = useState(props.defaultPipeline || pipelines[0])
  const [currentBranch, setCurrentBranch] = useState(props.defaultBranch || '')

  function handlePipelineSelect(event) {
    setCurrentPipeline(event.target.innerText)
    setIsPipelineOpen(false)
  }

  function handlePipelineToggle(isOpen) {
    setIsPipelineOpen(isOpen)
  }

  function handleBranchChange(newValue) {
    setCurrentBranch(newValue)
  }

  function handleInputSend(event) {
    // In case the event comes from a key press, only accept "Enter"
    if (event.key && event.key !== 'Enter') {
      return
    }

    // Ignore empty values
    if (!currentBranch) {
      return
    }

    // Clear the input field
    setCurrentBranch('')
    // Notify the parent component about the filter change
    props.onChange(currentPipeline, currentBranch)
  }

  function renderJobGraphToolbar () {
    return <>
      <Toolbar collapseListedFiltersBreakpoint="md">
        <ToolbarContent>
          <ToolbarToggleGroup breakpoint="md">
            <ToolbarGroup variant="filter-group">

              <ToolbarItem key="pipeline">
                <Dropdown
                  onSelect={handlePipelineSelect}
                  position={DropdownPosition.left}
                  toggle={
                    <DropdownToggle
                      onToggle={handlePipelineToggle}
                      style={{ width: '100%' }}
                    >
                      Pipeline: {currentPipeline}
                    </DropdownToggle>
                  }
                  isOpen={isPipelineOpen}
                  dropdownItems={pipelines.map((pipeline) => (
                    <DropdownItem key={pipeline}>{pipeline}</DropdownItem>
                  ))}
                  style={{ width: '100%' }}
                  menuAppendTo={document.body}
                />
              </ToolbarItem>

              <ToolbarItem key="branch">
                <TextInput
                  name="branch"
                  id="branch-input"
                  type="search"
                  placeholder="Branch"
                  defaultValue={props.defaultBranch}
                  onChange={handleBranchChange}
                  onKeyDown={(event) => handleInputSend(event)}
                />
              </ToolbarItem>

              <ToolbarItem key="button">
                <Button
                  onClick={(event) => handleInputSend(event)}
                >
                  View Job Graph
                </Button>
              </ToolbarItem>

            </ToolbarGroup>
          </ToolbarToggleGroup>
        </ToolbarContent>
      </Toolbar>
    </>
  }

  return (
    <div>
      {renderJobGraphToolbar()}
    </div>
  )
}

JobGraphToolbar.propTypes = {
  project: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  defaultBranch: PropTypes.string,
  defaultPipeline: PropTypes.string,
}

export default JobGraphToolbar
