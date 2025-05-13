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
  Chip,
  ChipGroup,
  Select,
  SelectOption,
  SelectVariant,
} from '@patternfly/react-core'


function FilterSelect(props) {
  const { filters, category } = props

  const [isOpen, setIsOpen] = useState(false)
  const [selected, setSelected] = useState(filters[category.key])
  const [options, setOptions] = useState(category.options)

  function onToggle(isOpen) {
    setSelected(filters[category.key])
    setIsOpen(isOpen)
  }

  function onSelect(event, selection) {
    const { onFilterChange, filters, category } = props

    const newSelected = selected.includes(selection)
      ? selected.filter(item => item !== selection)
      : [...selected, selection]

    setSelected(newSelected)
    const newFilters = {
      ...filters,
      [category.key]: newSelected,
    }
    onFilterChange(newFilters)
  }

  function onClear() {
    const { onFilterChange, filters, category } = props
    setSelected([])
    setIsOpen(false)
    const newFilters = {
      ...filters,
      [category.key]: [],
    }
    onFilterChange(newFilters)
  }

  function chipGroupComponent() {
    const { filters, category } = props
    const chipped = filters[category.key]
    return (
      <ChipGroup>
        {chipped.map((currentChip, index) => (
          <Chip
            isReadOnly={index === 0 ? true : false}
            key={currentChip}
            onClick={(e) => onSelect(e, currentChip)}
          >
            {currentChip}
          </Chip>
        ))}
      </ChipGroup>
    )
  }

  function onCreateOption(newValue) {
    const newOptions = [...options, newValue]
    setOptions(newOptions)
  }

  return (
    <Select
      chipGroupProps={{ numChips: 1, expandedText: 'Hide' }}
      variant={SelectVariant.typeaheadMulti}
      typeAheadAriaLabel={category.title}
      onToggle={onToggle}
      onClear={onClear}
      onSelect={onSelect}
      selections={filters[category.key]}
      isOpen={isOpen}
      isCreatable="true"
      onCreateOption={onCreateOption}
      placeholderText={category.placeholder}
      chipGroupComponent={chipGroupComponent}
      maxHeight={300}
    >
      {
        options.map((option, index) => (
          <SelectOption
            key={index}
            value={option}
          />
        ))
      }
    </Select >
  )
}

FilterSelect.propTypes = {
  onFilterChange: PropTypes.func.isRequired,
  filters: PropTypes.object.isRequired,
  category: PropTypes.object.isRequired,
}

export { FilterSelect }
