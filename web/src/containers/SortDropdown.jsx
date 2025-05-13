// Copyright 2025 BMW Group
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

import React, {useState} from 'react'
import PropTypes from 'prop-types'
import { Dropdown, DropdownItem, DropdownPosition, DropdownToggle, Tooltip } from '@patternfly/react-core'
import { SortAmountDownIcon } from '@patternfly/react-icons'

function getSearchKeyFromUrl(location, sortKeys) {
  const searchParams = new URLSearchParams(location.search)
  const searchKey = searchParams.get('sort')
  if (!searchKey) {
    return null
  }
  return sortKeys.find(k => k.key === searchKey)
}

function writeSearchKeyToUrl(sortKey, location, history) {
  const searchParams = new URLSearchParams(location.search)
  searchParams.set('sort', sortKey.key)
  history.push({
    pathname: location.pathname,
    search: searchParams.toString(),
  })
}

function SortDropdown({sortKeys, selectedSortKey, onSortKeyChange}) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)

  function onDropdownSelect(event) {
    const sortKey = sortKeys.find(k => k.title === event.target.innerText)
    onSortKeyChange(sortKey)
    setIsDropdownOpen(false)
  }

  return (
    <Tooltip content="Sort pipelines by...">
      <Dropdown
        position={DropdownPosition.left}
        onSelect={onDropdownSelect}
        toggle={
          <DropdownToggle
            onToggle={setIsDropdownOpen}>
              <SortAmountDownIcon/>&nbsp;
              {selectedSortKey.title}
          </DropdownToggle>
        }
        isOpen={isDropdownOpen}
        dropdownItems={sortKeys.map((k) =>
          <DropdownItem key={k.key}>{k.title}</DropdownItem>
        )}
      />
    </Tooltip>
  )
}

SortDropdown.propTypes = {
  sortKeys: PropTypes.array.isRequired,
  selectedSortKey: PropTypes.object.isRequired,
  onSortKeyChange: PropTypes.func.isRequired,
}

export { SortDropdown, getSearchKeyFromUrl, writeSearchKeyToUrl }

