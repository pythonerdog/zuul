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

import React, { useCallback, useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { connect, useDispatch } from 'react-redux'
import { withRouter, useLocation, useHistory } from 'react-router-dom'

import {
  Badge,
  Gallery,
  GalleryItem,
  Grid,
  GridItem,
  Level,
  LevelItem,
  PageSection,
  PageSectionVariants,
  Title,
  Text,
  TextContent,
  TextVariants,
  Toolbar,
  ToolbarContent,
  ToolbarItem,
  Tooltip,
  Switch,
} from '@patternfly/react-core'
import { StreamIcon } from '@patternfly/react-icons'

import ChangeQueue from '../containers/status/ChangeQueue'
import {
  countPipelineItems,
  isPipelineEmpty,
  PipelineIcon,
} from '../containers/status/Misc'
import { fetchStatusIfNeeded } from '../actions/status'
import { clearJobs } from '../actions/statusExpansion'
import { EmptyBox, EmptyPage } from '../containers/Errors'
import { Fetching, ReloadButton } from '../containers/Fetching'
import { useDocumentVisibility, useInterval } from '../Hooks'
import {
  FilterToolbar,
  getFiltersFromUrl,
  ToolbarStatsGroup,
  ToolbarStatsItem,
} from '../containers/FilterToolbar'
import {
  filterPipelines,
  handleFilterChange,
  filterInputValidation,
  clearFilters,
} from '../containers/status/Filters'

const filterCategories = (pipeline) => [
  {
    key: 'project',
    title: 'Project',
    placeholder: 'Filter by Project...',
    type: 'search',
    fuzzy: true,
  },
  {
    key: 'change',
    title: 'Change',
    placeholder: 'Filter by Change...',
    type: 'search',
    fuzzy: true,
  },
  {
    key: 'queue',
    title: 'Queue',
    placeholder: 'Filter by Queue...',
    type: 'select',
    // the last filter part makes sure we only provide options for queues
    // which have a non-empty name
    options: pipeline ? pipeline.change_queues.flat().map(q => q.name).filter(n => n): [],
    fuzzy: true,
  }
]

function PipelineDetails({ pipeline }) {

  const pipelineType = pipeline.manager || 'unknown'
  const itemCount = pipeline._count

  return (
    <>
      <Title headingLevel="h1">
        <PipelineIcon pipelineType={pipelineType} />
        {pipeline.name}
        <Tooltip
          content={
            itemCount === 1
              ? <div>{itemCount} item enqueued</div>
              : <div>{itemCount} items enqueued</div>
          }
        >
          <Badge
            isRead
            style={{
              marginLeft: 'var(--pf-global--spacer--sm)',
              verticalAlign: '0.1em',
              fontSize: 'var(--pf-global--FontSize--md)',
            }}
          >
            {itemCount}
          </Badge>
        </Tooltip>
      </Title>
      <Grid>
        <GridItem span={8}>
          <TextContent>
            <Text component={TextVariants.p}>
              {pipeline.description}
            </Text>
          </TextContent>
        </GridItem>
      </Grid>
    </>
  )
}

PipelineDetails.propTypes = {
  pipeline: PropTypes.object.isRequired,
}

function PipelineDetailsPage({
  pipeline, isFetching, tenant, darkMode, autoReload, fetchStatusIfNeeded, isEmpty
}) {
  const [isReloading, setIsReloading] = useState(false)
  const [isAllJobsExpanded, setIsAllJobsExpanded] = useState(
    localStorage.getItem('zuul_all_jobs_expanded') === 'true')

  const isDocumentVisible = useDocumentVisibility()

  const location = useLocation()
  const history = useHistory()
  const filters = getFiltersFromUrl(location, filterCategories(pipeline))
  const dispatch = useDispatch()

  const updateData = useCallback((tenant) => {
    if (tenant.name) {
      setIsReloading(true)
      fetchStatusIfNeeded(tenant)
        .then(() => {
          setIsReloading(false)
        })
    }
  }, [setIsReloading, fetchStatusIfNeeded])

  useEffect(() => {
    document.title = 'Zuul Pipeline Details'
    // Initial data fetch
    updateData(tenant)
  }, [updateData, tenant])


  // Subsequent data fetches every 5 seconds if auto-reload is enabled
  useInterval(() => {
    if (isDocumentVisible && autoReload) {
      updateData(tenant)
    }
    // Reset the interval on a manual refresh
  }, isReloading ? null : 5000)

  const onShowAllJobsToggle = (isChecked) => {
    setIsAllJobsExpanded(isChecked)
    localStorage.setItem('zuul_all_jobs_expanded', isChecked.toString())
    dispatch(clearJobs())
  }

  if (pipeline === undefined || (!isReloading && isFetching)) {
    return <Fetching />
  }

  if (!pipeline) {
    return (
      <EmptyPage
        title="This pipeline does not exist"
        icon={StreamIcon}
        linkTarget={`${tenant.linkPrefix}/status`}
        linkText="Back to status page"
      />
    )
  }

  return (
    <>
      <PageSection
        variant={darkMode ? PageSectionVariants.dark : PageSectionVariants.light}
        className="zuul-toolbar-section"
      >
        <Level>
          <LevelItem>
            <FilterToolbar
              filterCategories={filterCategories(pipeline)}
              onFilterChange={(newFilters) => { handleFilterChange(newFilters, filterCategories, location, history) }}
              filters={filters}
              filterInputValidation={filterInputValidation}
            >
              <ToolbarItem>
                <Switch
                  className="zuul-show-all-switch"
                  aria-label="Show all jobs"
                  label="Show all jobs"
                  isReversed
                  onChange={onShowAllJobsToggle}
                  isChecked={isAllJobsExpanded}
                />
              </ToolbarItem>
            </FilterToolbar>
          </LevelItem>
          <LevelItem>
            <Toolbar>
              <ToolbarContent style={{paddingRight: '0'}}>
                <ToolbarStatsGroup>
                  <ToolbarStatsItem
                    name="events"
                    value={`${pipeline.trigger_events} / ${pipeline.management_events} / ${pipeline.result_events}`}
                    tooltipContent={
                      <div>
                        Trigger events: {pipeline.trigger_events} <br />
                        Management events: {pipeline.management_events} <br />
                        Result events: {pipeline.result_events}
                      </div>
                    }
                  />
                  <ToolbarItem>
                    <ReloadButton
                      isReloading={isReloading}
                      reloadCallback={() => updateData(tenant)}
                    />
                  </ToolbarItem>
                </ToolbarStatsGroup>
              </ToolbarContent>
            </Toolbar>
          </LevelItem>
        </Level>
        <PipelineDetails pipeline={pipeline} />
      </PageSection>
      <PageSection
        variant={darkMode ? PageSectionVariants.dark : PageSectionVariants.light}
        className="zuul-main-section"
      >
        {!isEmpty &&
          <Title headingLevel="h3">
            <StreamIcon
              style={{
                marginRight: 'var(--pf-global--spacer--sm)',
                verticalAlign: '-0.1em',
              }}
            />{' '}
            Queues
          </Title>
        }
        <Gallery
          hasGutter
          minWidths={{
            sm: '400px',
          }}
        >
          {
            pipeline.change_queues.filter(
              queue => queue.heads.length > 0
            ).map((queue, idx) => (
              <GalleryItem key={idx}>
                <ChangeQueue queue={queue} pipeline={pipeline} jobsExpanded={isAllJobsExpanded} />
              </GalleryItem>
            ))
          }
        </Gallery>
        {isEmpty &&
          <EmptyBox
            title="No items found"
            icon={StreamIcon}
            action="Clear all filters"
            onAction={() => clearFilters(location, history, filterCategories(pipeline))}
          >
            No items match this filter criteria. Remove some filters or
            clear all to show results.
          </EmptyBox>
        }
      </PageSection>
    </>
  )
}

PipelineDetailsPage.propTypes = {
  match: PropTypes.object.isRequired,
  pipeline: PropTypes.object,
  isFetching: PropTypes.bool,
  tenant: PropTypes.object,
  darkMode: PropTypes.bool,
  autoReload: PropTypes.bool.isRequired,
  fetchStatusIfNeeded: PropTypes.func.isRequired,
  isEmpty: PropTypes.bool,
}

function mapStateToProps(state, ownProps) {
  let pipeline = null
  if (state.status.status) {
    const filters = getFiltersFromUrl(ownProps.location, filterCategories(null))
    // we need to work on a copy of the state..pipelines, because when mutating
    // the original, we couldn't reset or change the filters without reloading
    // from the backend first.
    const pipelines = global.structuredClone(state.status.status.pipelines)
    // Filter the state for this specific pipeline
    pipeline = filterPipelines(pipelines, filters, filterCategories(null), false)
      .find((p) => p.name === ownProps.match.params.pipelineName) || null
    pipeline = countPipelineItems(pipeline)
  }

  const isEmpty = pipeline && isPipelineEmpty(pipeline)

  return {
    pipeline,
    isFetching: state.status.isFetching,
    tenant: state.tenant,
    darkMode: state.preferences.darkMode,
    autoReload: state.preferences.autoReload,
    isEmpty,
  }
}

const mapDispatchToProps = { fetchStatusIfNeeded }

export default connect(
  mapStateToProps,
  mapDispatchToProps,
)(withRouter(PipelineDetailsPage))
