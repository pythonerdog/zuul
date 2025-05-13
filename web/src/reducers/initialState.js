export default {
  build: {
    builds: {},
    buildsets: {},
    // Store outputs, manifest, hosts and errorIds separately from the build.
    // This allows us to fetch everything in parallel and we don't have to wait
    // until the build is available. We also don't have to update the actual
    // build object with new information everytime.
    // To simplify the usage we can map everything into a single build object
    // in the mapStateToProps() function in the build page.
    outputs: {},
    manifests: {},
    hosts: {},
    errorIds: {},
    isFetching: false,
    isFetchingOutput: false,
    isFetchingManifest: false,
  },
  component: {
    components: undefined,
    isFetching: false,
  },
  logfile: {
    // Store files by buildId->filename->content
    files: {},
    isFetching: true,
    url: null,
  },
  auth: {},
  user: {},
}
