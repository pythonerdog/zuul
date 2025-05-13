import { createStore } from 'redux'

import rootReducer from './reducers'
import initialState from './reducers/initialState'
import * as buildActions from './actions/build'

it('should fetch a build', () => {
  const store = createStore(rootReducer, initialState)
  const build = {
    uuid: '1234',
    job_name: 'run-tox',
  }

  const action = buildActions.receiveBuild(build.uuid, build)
  store.dispatch(action)

  const fetchedBuild = store.getState().build.builds[build.uuid]
  expect(fetchedBuild).toEqual(build)
})

it('should fetch an output', () => {
  const store = createStore(rootReducer, initialState)
  const build = {
    uuid: '1234',
    job_name: 'run-tox',
  }
  const output = [
    {
      branch: 'master',
      index: '0',
      phase: 'pre',
      playbook: 'opendev.org/opendev/base-jobs/playbooks/base/pre.yaml',
      plays: [
        {
          play: {
            duration: {
              end: '2020-09-24T23:24:02.272988Z',
              start: '2020-09-24T23:23:52.900231Z',
            },
            id: 'bc764e04-8d26-889a-2270-000000000006',
            name: 'localhost',
          },
          tasks: [
            {
              hosts: {
                localhost: {
                  action: 'include_role',
                  changed: false,
                  include_args: {
                    name: 'set-zuul-log-path-fact',
                  },
                },
              },
              role: {
                id: 'bc764e04-8d26-889a-2270-000000000009',
                name: 'emit-job-header',
                path:
                  '/var/lib/zuul/builds/79dea00ae4dd4943a09a8bb701488bb5/trusted/project_1/opendev.org/zuul/zuul-jobs/roles/emit-job-header',
              },
              task: {
                duration: {
                  end: '2020-09-24T23:23:55.818592Z',
                  start: '2020-09-24T23:23:55.724571Z',
                },
                id: 'bc764e04-8d26-889a-2270-00000000000c',
                name: 'Setup log path fact',
              },
            },
          ],
        },
      ],
      stats: {
        localhost: {
          changed: 2,
          failures: 0,
          ignored: 0,
          ok: 6,
          rescued: 0,
          skipped: 5,
          unreachable: 0,
        },
        'ubuntu-bionic': {
          changed: 22,
          failures: 0,
          ignored: 0,
          ok: 47,
          rescued: 0,
          skipped: 7,
          unreachable: 0,
        },
      },
      trusted: true,
    },
  ]

  // Fetch the output
  store.dispatch(buildActions.receiveBuildOutput(build.uuid, output))

  const newState = store.getState()
  expect(Object.keys(newState.build.outputs).length).toEqual(1)
  expect(Object.keys(newState.build.hosts).length).toEqual(1)
  expect(Object.keys(newState.build.errorIds).length).toEqual(1)

  const expectedHosts = {
    localhost: {
      changed: 2,
      failures: 0,
      ignored: 0,
      ok: 6,
      rescued: 0,
      skipped: 5,
      unreachable: 0,
      failed: [],
    },
    'ubuntu-bionic': {
      changed: 22,
      failures: 0,
      ignored: 0,
      ok: 47,
      rescued: 0,
      skipped: 7,
      unreachable: 0,
      failed: [],
    },
  }

  const fetchedOutput = newState.build.outputs[build.uuid]
  const fetchedHosts = newState.build.hosts[build.uuid]
  const fetchedErrorIds = newState.build.errorIds[build.uuid]
  expect(fetchedOutput).toEqual(output)
  expect(fetchedHosts).toEqual(expectedHosts)
  expect(fetchedErrorIds).toEqual(new Set())
})

it('should fetch a manifest file', () => {
  const store = createStore(rootReducer, initialState)
  const build = {
    uuid: '1234',
    job_name: 'run-tox',
  }
  const manifest = {
    tree: [
      {
        name: 'zuul-info',
        mimetype: 'application/directory',
        encoding: null,
        children: [
          {
            name: 'host-info.ubuntu-bionic.yaml',
            mimetype: 'text/plain',
            encoding: null,
            last_modified: 1600989879,
            size: 12895,
          },
          {
            name: 'inventory.yaml',
            mimetype: 'text/plain',
            encoding: null,
            last_modified: 1600989840,
            size: 3734,
          },
          {
            name: 'zuul-info.ubuntu-bionic.txt',
            mimetype: 'text/plain',
            encoding: null,
            last_modified: 1600989881,
            size: 2584,
          },
        ],
      },
      {
        name: 'job-output.json',
        mimetype: 'application/json',
        encoding: null,
        last_modified: 1600990084,
        size: 612933,
      },
      {
        name: 'job-output.txt',
        mimetype: 'text/plain',
        encoding: null,
        last_modified: 1600990088,
        size: 84764,
      },
    ],
  }

  // Fetch the manifest
  store.dispatch(buildActions.receiveBuildManifest(build.uuid, manifest))

  const newState = store.getState()
  expect(Object.keys(newState.build.manifests).length).toEqual(1)

  const expectedManifestIndex = {
    '/zuul-info/host-info.ubuntu-bionic.yaml': {
      name: 'host-info.ubuntu-bionic.yaml',
      mimetype: 'text/plain',
      encoding: null,
      last_modified: 1600989879,
      size: 12895,
    },
    '/zuul-info/inventory.yaml': {
      name: 'inventory.yaml',
      mimetype: 'text/plain',
      encoding: null,
      last_modified: 1600989840,
      size: 3734,
    },
    '/zuul-info/zuul-info.ubuntu-bionic.txt': {
      name: 'zuul-info.ubuntu-bionic.txt',
      mimetype: 'text/plain',
      encoding: null,
      last_modified: 1600989881,
      size: 2584,
    },
    '/job-output.json': {
      name: 'job-output.json',
      mimetype: 'application/json',
      encoding: null,
      last_modified: 1600990084,
      size: 612933,
    },
    '/job-output.txt': {
      name: 'job-output.txt',
      mimetype: 'text/plain',
      encoding: null,
      last_modified: 1600990088,
      size: 84764,
    },
  }

  const fetchedManifest = newState.build.manifests[build.uuid]
  expect(fetchedManifest).toEqual({
    index: expectedManifestIndex,
    tree: manifest.tree,
  })
})
