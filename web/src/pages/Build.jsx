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

import * as React from 'react'
import { connect } from 'react-redux'
import { withRouter } from 'react-router-dom'
import PropTypes from 'prop-types'
import { parse } from 'query-string'
import {
  Button,
  EmptyState,
  EmptyStateVariant,
  EmptyStateIcon,
  PageSection,
  PageSectionVariants,
  Tab,
  Tabs,
  TabTitleIcon,
  TabTitleText,
  Title,
} from '@patternfly/react-core'
import {
  ArrowUpIcon,
  BuildIcon,
  FileArchiveIcon,
  FileCodeIcon,
  TerminalIcon,
  PollIcon,
  ExclamationIcon,
} from '@patternfly/react-icons'

import { fetchBuildAllInfo } from '../actions/build'
import { fetchLogfile } from '../actions/logfile'
import { EmptyPage } from '../containers/Errors'
import { Fetching } from '../containers/Fetching'
import ArtifactList from '../containers/build/Artifact'
import Build from '../containers/build/Build'
import BuildOutput from '../containers/build/BuildOutput'
import Console from '../containers/build/Console'
import Manifest from '../containers/build/Manifest'
import LogFile from '../containers/logfile/LogFile'

class BuildPage extends React.Component {
  static propTypes = {
    match: PropTypes.object.isRequired,
    build: PropTypes.object,
    logfile: PropTypes.object,
    isFetching: PropTypes.bool.isRequired,
    isFetchingManifest: PropTypes.bool.isRequired,
    isFetchingOutput: PropTypes.bool.isRequired,
    isFetchingLogfile: PropTypes.bool.isRequired,
    tenant: PropTypes.object.isRequired,
    fetchBuildAllInfo: PropTypes.func.isRequired,
    activeTab: PropTypes.string.isRequired,
    location: PropTypes.object.isRequired,
    history: PropTypes.object.isRequired,
    preferences: PropTypes.object,
  }

  state = {
    topOfPageVisible: true,
  }

  updateData = () => {
    // The related fetchBuild...() methods won't do anything if the data is
    // already available in the local state, so just call them.
    this.props.fetchBuildAllInfo(
      this.props.tenant,
      this.props.match.params.buildId,
      this.props.match.params.file
    )
  }

  onScroll = () => {
    this.setState({topOfPageVisible: window.scrollY === 0})
  }

  componentDidMount() {
    document.title = 'Zuul Build'
    if (this.props.tenant.name) {
      this.updateData()
    }
    window.addEventListener('scroll', this.onScroll)
  }

  componentDidUpdate(prevProps) {
    if (this.props.tenant.name !== prevProps.tenant.name) {
      this.updateData()
    }
  }

  handleTabClick = (tabIndex, build) => {
    // Usually tabs should only be used to display content in-page and not link
    // to other pages:
    // "Tabs are used to present a set on tabs for organizing content on a
    // .page. It must always be used together with a tab content component."
    // https://www.patternfly.org/v4/documentation/react/components/tabs
    // But as want to be able to reach every tab's content via a dedicated URL
    // while having the look and feel of tabs, we could hijack this onClick
    // handler to do the link/routing stuff.
    const { history, tenant } = this.props

    switch (tabIndex) {
      case 'artifacts':
        history.push(`${tenant.linkPrefix}/build/${build.uuid}/artifacts`)
        break
      case 'logs':
        history.push(`${tenant.linkPrefix}/build/${build.uuid}/logs`)
        break
      case 'console':
        history.push(`${tenant.linkPrefix}/build/${build.uuid}/console`)
        break
      default:
        // task summary
        history.push(`${tenant.linkPrefix}/build/${build.uuid}`)
    }
  }

  handleBreadcrumbItemClick = () => {
    // Simply link back to the logs tab without an active logfile
    this.handleTabClick('logs', this.props.build)
  }

  render() {
    const {
      build,
      logfile,
      isFetching,
      isFetchingManifest,
      isFetchingOutput,
      isFetchingLogfile,
      activeTab,
      history,
      location,
      tenant,
    } = this.props
    const hash = location.hash.substring(1).split('/')
    const severity = parseInt(parse(location.search).severity)

    // Get the logfile from react-routers URL parameters
    const logfileName = this.props.match.params.file

    // In case the build is not available yet (before the fetching started) or
    // is currently fetching.
    if (build === undefined || isFetching) {
      return <Fetching />
    }

    // The build is null, meaning it couldn't be found.
    if (!build) {
      return (
        <EmptyPage
          title="This build does not exist"
          icon={BuildIcon}
          linkTarget={`${tenant.linkPrefix}/builds`}
          linkText="Show all builds"
        />
      )
    }

    const resultsTabContent =
      build.hosts === undefined || isFetchingOutput ? (
        <Fetching />
      ) : build.hosts ? (
        <BuildOutput output={build.hosts} />
      ) : build.error_detail ? (
        <>
        <EmptyState variant={EmptyStateVariant.small}>
          <EmptyStateIcon icon={ExclamationIcon} />
        </EmptyState>
          <p><b>Error:</b> {build.error_detail}</p>
        </>
      ) : (
        <EmptyState variant={EmptyStateVariant.small}>
          <EmptyStateIcon icon={PollIcon} />
          <Title headingLevel="h4" size="lg">
            This build does not provide any results
          </Title>
        </EmptyState>
      )

    const artifactsTabContent = build.artifacts.length ? (
      <ArtifactList artifacts={build.artifacts} />
    ) : (
      <EmptyState variant={EmptyStateVariant.small}>
        <EmptyStateIcon icon={FileArchiveIcon} />
        <Title headingLevel="h4" size="lg">
          This build does not provide any artifacts
        </Title>
      </EmptyState>
    )

    let logsTabContent = null
    if (build.manifest === undefined || isFetchingManifest) {
      logsTabContent = <Fetching />
    } else if (logfileName) {
      logsTabContent = (
        <LogFile
          logfileContent={logfile}
          logfileName={logfileName}
          isFetching={isFetchingLogfile}
          // We let the LogFile component itself handle the severity default
          // value in case it's not set via the URL.
          severity={severity ? severity : undefined}
          handleBreadcrumbItemClick={this.handleBreadcrumbItemClick}
          location={location}
          history={history}
        />
      )
    // Do not render the Manifest component if we don't have a log_url (this
    // can happen for CANCELLED builds) since the log file paths are
    // constructed from the build.log_url. Instead show the EmptyState.
    } else if (build.manifest && build.log_url) {
      logsTabContent = <Manifest tenant={this.props.tenant} build={build} />
    } else {
      logsTabContent = (
        <EmptyState variant={EmptyStateVariant.small}>
          <EmptyStateIcon icon={FileCodeIcon} />
          <Title headingLevel="h4" size="lg">
            This build does not provide any logs
          </Title>
        </EmptyState>
      )
    }

    const consoleTabContent =
      build.output === undefined || isFetchingOutput ? (
        <Fetching />
      ) : build.output ? (
        <Console
          output={build.output}
          errorIds={build.errorIds}
          displayPath={hash.length > 0 ? hash : undefined}
        />
      ) : (
        <EmptyState variant={EmptyStateVariant.small}>
          <EmptyStateIcon icon={TerminalIcon} />
          <Title headingLevel="h4" size="lg">
            This build does not provide any console information
          </Title>
        </EmptyState>
      )

    return (
      <>
        <PageSection variant={this.props.preferences.darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
          <Build build={build} active={activeTab} hash={hash} />
        </PageSection>
        <PageSection variant={this.props.preferences.darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
          <Tabs
            isFilled
            activeKey={activeTab}
            onSelect={(event, tabIndex) => this.handleTabClick(tabIndex, build)}
          >
            <Tab
              eventKey="results"
              title={
                <>
                  <TabTitleIcon>
                    <PollIcon />
                  </TabTitleIcon>
                  <TabTitleText>Task Summary</TabTitleText>
                </>
              }
            >
              {resultsTabContent}
            </Tab>
            <Tab
              eventKey="artifacts"
              title={
                <>
                  <TabTitleIcon>
                    <FileArchiveIcon />
                  </TabTitleIcon>
                  <TabTitleText>Artifacts</TabTitleText>
                </>
              }
            >
              {artifactsTabContent}
            </Tab>
            <Tab
              eventKey="logs"
              title={
                <>
                  <TabTitleIcon>
                    <FileCodeIcon />
                  </TabTitleIcon>
                  <TabTitleText>Logs</TabTitleText>
                </>
              }
            >
              {logsTabContent}
            </Tab>
            <Tab
              eventKey="console"
              title={
                <>
                  <TabTitleIcon>
                    <TerminalIcon />
                  </TabTitleIcon>
                  <TabTitleText>Console</TabTitleText>
                </>
              }
            >
              {consoleTabContent}
            </Tab>
          </Tabs>
        </PageSection>
        {!this.state.topOfPageVisible && (
          <PageSection variant={this.props.preferences.darkMode ? PageSectionVariants.dark : PageSectionVariants.light}>
            <Button onClick={scrollToTop} variant="primary" style={{position: 'fixed', bottom: 20, right: 20, zIndex: 1}}>
              Go to top of page <ArrowUpIcon/>
            </Button>
          </PageSection>
        )}
      </>
    )
  }
}

function scrollToTop() {
  window.scrollTo(0,0)
  document.activeElement.blur()
}

function mapStateToProps(state, ownProps) {
  const buildId = ownProps.match.params.buildId
  // JavaScript will return undefined in case the key is missing in the
  // dict/object.
  const buildFromState = state.build.builds[buildId]
  // Only copy the build if it's a valid object. In case it is null or undefined
  // directly assign the value. The cloning is necessary as we mutate the build
  // in the next step when adding the manifest, output, ... information.
  const build = buildFromState ? { ...buildFromState } : buildFromState

  // If the build is available, extend it with more information. All those
  // values will be undefined if they are not part of the dict/object.
  if (build) {
    build.manifest = state.build.manifests[buildId]
    build.output = state.build.outputs[buildId]
    build.hosts = state.build.hosts[buildId]
    build.errorIds = state.build.errorIds[buildId]
  }
  const logfileName = ownProps.match.params.file
  const logfile =
    buildId in state.logfile.files
      ? state.logfile.files[buildId][logfileName]
      : undefined

  return {
    build,
    logfile,
    tenant: state.tenant,
    isFetching: state.build.isFetching,
    isFetchingManifest: state.build.isFetchingManifest,
    isFetchingOutput: state.build.isFetchingOutput,
    isFetchingLogfile: state.logfile.isFetching,
    preferences: state.preferences,
  }
}

const mapDispatchToProps = { fetchBuildAllInfo, fetchLogfile }

export default connect(
  mapStateToProps,
  mapDispatchToProps
)(withRouter(BuildPage))
