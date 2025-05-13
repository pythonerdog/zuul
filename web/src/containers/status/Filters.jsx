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

import { applyFilter, isFilterActive, writeFiltersToUrl } from '../FilterToolbar'
import { isPipelineEmpty } from './Misc'

function handleFilterChange(newFilters, filterCategories, location, history) {
  writeFiltersToUrl(newFilters, filterCategories, location, history)
}

function clearFilters(location, history, filterCategories) {
  // Delete the values for each filter category
  const filters = filterCategories.reduce((filterDict, category) => {
    filterDict[category.key] = []
    return filterDict
  }, {})
  handleFilterChange(filters, filterCategories, location, history)
}

function filterInputValidation(_, filterValue) {
  // Input value should not be empty for all cases
  if (!filterValue) {
    return {
      success: false,
      message: 'Input should not be empty'
    }
  }

  return {
    success: true
  }
}

function filterByPipeline(pipelines, filter, fuzzy) {
  return pipelines.filter(p => applyFilter([p.name], filter, fuzzy))
}

function filterByQueue(pipelines, filter, fuzzy, truncateEmpty) {
  for (const p of pipelines) {
    p.change_queues = p.change_queues.filter(
      q => applyFilter([q.name], filter, fuzzy)
    )
  }

  // when searching for specific queues, we want to hide pipelines that are now
  // empty on the PipelineOverview page and only show those with matches for
  // the filter (truncateEmpty is true).
  // On the PipelineDetails page, we don't want to get rid of an empty
  // pipeline, instead present the user an "your filter did not match any
  // items" result. Otherwise, we run into a state where the PipelineDetails
  // page presents a "this pipeline does not exist" result (so we set
  // truncateEmpty to false).
  if (truncateEmpty) {
    return pipelines.filter(p => !isPipelineEmpty(p))
  }
  return pipelines
}

function filterByProject(pipelines, filter, fuzzy, truncateEmpty) {
  for (const p of pipelines) {
    for (const q of p.change_queues) {
      const heads = []
      for (const head of q.heads) {
        heads.push(head.filter(item => {
          const projects = item.refs.map(ref => ref.project)
          return applyFilter(projects, filter, fuzzy)
        }))
      }
      // if we found a match on an unnamed queue, we want to display the entire
      // queue, ie. we want to also display non-live items ahead of matched one
      if (heads.flat().length === 0 || q.name !== '') {
        q.heads = heads
      }
    }
  }

  // when searching for single items, we want to hide empty pipelines except
  // for when we're on the PipelineDetails page for the same reasons as above
  // (cf. filterByQueue)
  if (truncateEmpty) {
    pipelines = pipelines.filter(p => !isPipelineEmpty(p))
  }
  for (const p of pipelines) {
    p.change_queues = p.change_queues.filter(q => q.heads.flat().length > 0)
  }
  return pipelines
}

function filterByChange(pipelines, filter, fuzzy, truncateEmpty) {
  // Here we filter for change number without the ref part. So we are only
  // interested in the first part of the id being of format
  // {change_num},{patchset/commit}.
  // Or by a full match of the input, e.g. when filtering for a ref instead of
  // a change number
  const _filter = filter.map(f => [`${f},*`, `${f}`]).flat()
  for (const p of pipelines) {
    for (const q of p.change_queues) {
      const heads = []
      for (const head of q.heads) {
        heads.push(head.filter(item => {
          const ids = item.refs.map(ref => ref.id || ref.ref)
          return applyFilter(ids, _filter, fuzzy)
        }))
      }
      // if we found a match on an unnamed queue, we want to display the entire
      // queue, ie. we want to also display non-live items ahead of matched one
      if (heads.flat().length === 0 || q.name !== '') {
        q.heads = heads
      }
    }
  }

  // when searching for single items, we want to hide empty pipelines except
  // for when we're on the PipelineDetails page for the same reasons as above
  // (cf. filterByQueue)
  if (truncateEmpty) {
    pipelines = pipelines.filter(p => !isPipelineEmpty(p))
  }
  for (const p of pipelines) {
    p.change_queues = p.change_queues.filter(q => q.heads.flat().length > 0)
  }
  return pipelines
}

function filterPipelines(pipelines, filters, filterCategories, truncateEmpty) {
  if (!isFilterActive(filters)) {
    return pipelines
  }

  // get rid of limit/skip pagination filters that come from the FilterToolbar
  // by going over the valid FILTER_CATEGORIES
  for (const category of filterCategories) {
    const key = category['key']
    const fuzzy = category['fuzzy']
    const filter = filters[key]
    if (filter.length === 0) {
      continue
    }

    switch (key) {
      case 'pipeline':
        pipelines = filterByPipeline(pipelines, filter, fuzzy)
        break
      case 'queue':
        pipelines = filterByQueue(pipelines, filter, fuzzy, truncateEmpty)
        break
      case 'project':
        pipelines = filterByProject(pipelines, filter, fuzzy, truncateEmpty)
        break
      case 'change': {
        pipelines = filterByChange(pipelines, filter, fuzzy, truncateEmpty)
        break
      }
      default:
        // this should not happen
        break
    }
  }

  return pipelines
}

export {
  clearFilters,
  filterInputValidation,
  filterPipelines,
  handleFilterChange,
}
