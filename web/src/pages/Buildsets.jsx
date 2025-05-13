// Copyright 2019 Red Hat, Inc
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
import { isEqual } from 'lodash'
import PropTypes from 'prop-types'
import { connect } from 'react-redux'
import { PageSection, PageSectionVariants, Pagination } from '@patternfly/react-core'

import { fetchBuildsets } from '../api'
import {
  FilterToolbar,
  getFiltersFromUrl,
  writeFiltersToUrl,
} from '../containers/FilterToolbar'
import { makeBuildsetQueryString } from '../containers/BuildQuery'
import BuildsetTable from '../containers/build/BuildsetTable'

class BuildsetsPage extends React.Component {
  static propTypes = {
    tenant: PropTypes.object,
    location: PropTypes.object,
    history: PropTypes.object,
    preferences: PropTypes.object,
  }

  constructor(props) {
    super()
    this.filterCategories = [
      {
        key: 'project',
        title: 'Project',
        placeholder: 'Filter by Project...',
        type: 'search',
        fuzzy: true,
      },
      {
        key: 'branch',
        title: 'Branch',
        placeholder: 'Filter by Branch...',
        type: 'search',
        fuzzy: true,
      },
      {
        key: 'pipeline',
        title: 'Pipeline',
        placeholder: 'Filter by Pipeline...',
        type: 'search',
        fuzzy: true,
      },
      {
        key: 'change',
        title: 'Change',
        placeholder: 'Filter by Change...',
        type: 'search',
        fuzzy: false,
      },
      {
        key: 'result',
        title: 'Result',
        placeholder: 'Filter by Result...',
        type: 'select',
        options: [
          'SUCCESS',
          'FAILURE',
          'MERGE_CONFLICT',
          'MERGE_FAILURE',
          'DEQUEUED',
          'CONFIG_ERROR',
          'NO_JOBS',
        ],
        fuzzy: false,
      },
      {
        key: 'uuid',
        title: 'Buildset',
        placeholder: 'Filter by Buildset UUID...',
        type: 'search',
        fuzzy: false,
      },
    ]

    const _filters = getFiltersFromUrl(props.location, this.filterCategories)
    const perPage = _filters.limit[0]
      ? parseInt(_filters.limit[0])
      : 50
    const currentPage = _filters.skip[0]
      ? Math.floor(parseInt(_filters.skip[0] / perPage)) + 1
      : 1

    this.state = {
      buildsets: [],
      fetching: false,
      filters: _filters,
      resultsPerPage: perPage,
      currentPage: currentPage,
      itemCount: null,
    }
  }

  updateData = (filters) => {
    // When building the filter query for the API we can't rely on the location
    // search parameters. Although, we've updated them in the updateUrl() method
    // they always have the same value in here (the values when the page was
    // first loaded). Most probably that's the case because the location is
    // passed as prop and doesn't change since the page itself wasn't
    // re-rendered.
    const { itemCount } = this.state
    let paginationOptions = {
      skip: filters.skip.length > 0 ? filters.skip : [0,],
      limit: filters.limit.length > 0 ? filters.limit : [50,]
    }
    let _filters = { ...filters, ...paginationOptions }
    const queryString = makeBuildsetQueryString(_filters)
    this.setState({ fetching: true })
    fetchBuildsets(this.props.tenant.apiPrefix, queryString).then(
      (response) => {
        // if we have already an itemCount for this query (ie we're scrolling backwards through results)
        // keep this value. Otherwise, check if we've got all the results.
        let finalItemCount = itemCount
          ? itemCount
          : (response.data.length < paginationOptions.limit[0]
            ? parseInt(paginationOptions.skip[0]) + response.data.length
            : null)
        this.setState({
          buildsets: response.data,
          fetching: false,
          itemCount: finalItemCount,
        })
      }
    )
  }

  componentDidMount() {
    document.title = 'Zuul Buildsets'
    if (this.props.tenant.name) {
      this.updateData(this.state.filters)
    }
  }

  componentDidUpdate(prevProps) {
    const { filters } = this.state
    if (this.props.tenant.name !== prevProps.tenant.name) {
      this.updateData(filters)
    }
  }

  filterInputValidation = (filterKey, filterValue) => {
    // Input value should not be empty for all cases
    if (!filterValue) {
      return {
        success: false,
        message: 'Input should not be empty'
      }
    }

    // For change filter, it must be an integer
    if (filterKey === 'change' && isNaN(filterValue)) {
      return {
        success: false,
        message: 'Change must be an integer (do not include revision)'
      }
    }

    return {
      success: true
    }
  }

  handleFilterChange = (newFilters) => {
    const { location, history } = this.props
    const { filters, itemCount } = this.state
    /*eslint no-unused-vars: ["error", { "ignoreRestSiblings": true }]*/
    let { 'skip': x1, 'limit': y1, ..._oldFilters } = filters
    let { 'skip': x2, 'limit': y2, ..._newFilters } = newFilters

    // If filters have changed, reinitialize skip
    let equalTest = isEqual(_oldFilters, _newFilters)
    let finalFilters = equalTest ? newFilters : { ...newFilters, skip: [0,] }

    // We must update the URL parameters before the state. Otherwise, the URL
    // will always be one filter selection behind the state. But as the URL
    // reflects our state this should be ok.

    writeFiltersToUrl(newFilters, this.filterCategories, location, history)
    let newState = {
      filters: finalFilters,
      // if filters haven't changed besides skip or limit, keep our itemCount and currentPage
      itemCount: equalTest ? itemCount : null,
    }
    if (!equalTest) {
      newState.currentPage = 1
    }
    this.setState(
      newState,
      () => {
        this.updateData(finalFilters)
      })
  }

  handleClearFilters = () => {
    // Delete the values for each filter category
    const filters = this.filterCategories.reduce((filterDict, category) => {
      filterDict[category.key] = []
      return filterDict
    }, {})
    this.handleFilterChange(filters)
  }

  handlePerPageSelect = (event, perPage) => {
    const { filters } = this.state
    this.setState({ resultsPerPage: perPage })
    const newFilters = { ...filters, limit: [perPage,] }
    this.handleFilterChange(newFilters)
  }

  handleSetPage = (event, pageNumber) => {
    const { filters, resultsPerPage } = this.state
    this.setState({ currentPage: pageNumber })
    const offset = resultsPerPage * (pageNumber - 1)
    const newFilters = { ...filters, skip: [offset,] }
    this.handleFilterChange(newFilters)
  }

  render() {
    const { history } = this.props
    const { buildsets, fetching, filters, resultsPerPage, currentPage, itemCount } = this.state

    return (
      <PageSection variant={this.props.preferences.darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
        <FilterToolbar
          filterCategories={this.filterCategories}
          onFilterChange={this.handleFilterChange}
          filters={filters}
          filterInputValidation={this.filterInputValidation}
        />
        <Pagination
          toggleTemplate={({ firstIndex, lastIndex, itemCount }) => (
            <React.Fragment>
              <b>
                {firstIndex} - {lastIndex}
              </b>
              &nbsp;
              of
              &nbsp;
              <b>{itemCount ? itemCount : 'many'}</b>
            </React.Fragment>
          )}
          itemCount={itemCount}
          perPage={resultsPerPage}
          page={currentPage}
          widgetId="pagination-menu"
          onPerPageSelect={this.handlePerPageSelect}
          onSetPage={this.handleSetPage}
          isCompact
        />
        <BuildsetTable
          buildsets={buildsets}
          fetching={fetching}
          onClearFilters={this.handleClearFilters}
          history={history}
        />
      </PageSection>
    )
  }
}

export default connect((state) => ({
  tenant: state.tenant,
  preferences: state.preferences,
}))(BuildsetsPage)
