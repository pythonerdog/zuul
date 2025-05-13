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

import React, { useState } from 'react'
import PropTypes from 'prop-types'

import {
  Select,
  SelectOption,
  SelectVariant,
} from '@patternfly/react-core'


function FilterTernarySelect(props) {
  /* The ternary select expects the options to be in order: All/True/False */
  const { filters, category } = props

  const [isOpen, setIsOpen] = useState(false)
  const options = category.options
  const _getSelected = (value) => {
    switch (value) {
      case 1:
      case '1':
        return category.options[1]
      case 0:
      case '0':
        return category.options[2]
      default:
        return null
    }
  }
  let _selected = _getSelected([...filters[category.key]].pop())
  const [selected, setSelected] = useState(_selected)

  function onToggle(isOpen) {
    setIsOpen(isOpen)
  }

  function onSelect(event, selection) {
    const { onFilterChange, filters, category } = props

    let _selection = (selection === selected) ? null : selection

    setSelected(_selection)
    const setNewFilter = (value) => {
      switch (value) {
        case category.options[1]:
          return [1,]
        case category.options[2]:
          return [0,]
        default:
          return []
      }
    }
    const newFilters = {
      ...filters,
      [category.key]: setNewFilter(_selection),
    }
    onFilterChange(newFilters)
    setIsOpen(false)
  }

  function onClear() {
    const { onFilterChange, filters, category } = props
    setSelected(null)
    setIsOpen(false)
    const newFilters = {
      ...filters,
      [category.key]: [],
    }
    onFilterChange(newFilters)
  }

  return (
    <Select
      variant={SelectVariant.single}
      placeholderText={category.placeholder}
      isOpen={isOpen}
      onToggle={onToggle}
      onSelect={onSelect}
      onClear={onClear}
      selections={_selected}
    >
      {
        options.map((option, index) => (
          <SelectOption
            key={index}
            value={option}
          />
        ))
      }
    </Select>
  )
}

FilterTernarySelect.propTypes = {
  onFilterChange: PropTypes.func.isRequired,
  filters: PropTypes.object.isRequired,
  category: PropTypes.object.isRequired,
}

export { FilterTernarySelect }