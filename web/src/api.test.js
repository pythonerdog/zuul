import { getHomepageUrl, getLogFile, setAuthToken } from './api'
import axios from 'axios'
jest.mock('axios')

afterEach(() => {
  jest.clearAllMocks()
})

it('should should return the homepage url', () => {
  const homepage = 'https://my-zuul.com/'
  Object.defineProperty(window, 'location', {
    value: new URL(homepage)
  } )

  // Test some of the known, possible, URLs to verify
  // that the origin is returned.
  const urls = [
      // auth_callback test  as some providers build
      // different callback urls
      'https://my-zuul.com/auth_callback',
      'https://my-zuul.com/auth_callback#state=12345',

      // Regular browser navigation urls
      'https://my-zuul.com/status',
      'https://my-zuul.com/t/zuul-tenant/status',
      'https://my-zuul.com/t/zuul-tenant/jobs',

      // API urls
      'https://my-zuul.com/api/tenant/zuul-tenant/status',
      'https://my-zuul.com/api/tenant/zuul-tenant/authorization',

  ]

  for (let url of urls) {
    window.location.href = url
    expect(getHomepageUrl()).toEqual(homepage)
  }
})

it('should return the subdir homepage url', () => {
   const homepage = 'https://example.com/zuul/'
   Object.defineProperty(window, 'location', {
     value: new URL(homepage)
   } )
   // The build process strips trailing slashes from PUBLIC_URL,
   // so make sure we don't include any in our tests
   Object.defineProperty(process.env, 'PUBLIC_URL', {
     value: '/zuul'
   } )

   // Test some of the known, possible, URLs to verify
   // that the origin is returned.
   const urls = [
       // auth_callback test  as some providers build
       // different callback urls
       'https://example.com/zuul/auth_callback',
       'https://example.com/zuul/auth_callback#state=12345',

       // Regular browser navigation urls
       'https://example.com/zuul/status',
       'https://example.com/zuul/t/zuul-tenant/status',
       'https://example.com/zuul/t/zuul-tenant/jobs',
   ]

   for (let url of urls) {
     window.location.href = url
     expect(getHomepageUrl()).toEqual(homepage)
   }
 })

it('should not request logs with auth header per default', () => {
  Object.defineProperty(process.env, 'REACT_APP_ZUUL_API', {
    value: 'https://example.com/api/'
  })

  // same origin but we're not expecting auth headers, because
  // we have not explicitly enabled that
  const logFileUrl = 'https://example.com/logs/build-output.txt'
  setAuthToken('foobar')

  getLogFile(logFileUrl, false)
  expect(axios.get).toHaveBeenCalledTimes(1)
  expect(axios.get).toHaveBeenCalledWith(logFileUrl, { headers: {} })
})

it('should request logs with auth header if enabled', () => {
  Object.defineProperty(process.env, 'REACT_APP_ZUUL_API', {
    value: 'https://example.com/api/'
  })

  const logFileUrl = 'https://example.com/logs/build-output.txt'
  setAuthToken('foobar')

  getLogFile(logFileUrl, true)
  expect(axios.get).toHaveBeenCalledTimes(1)
  expect(axios.get).toHaveBeenCalledWith(logFileUrl, {
    headers: { Authorization: 'Bearer foobar' }
  })
})

it('should request logs without auth header if origins don\'t match', () => {
  Object.defineProperty(process.env, 'REACT_APP_ZUUL_API', {
    value: 'https://example.com/api/'
  })

  // api and log endpoint have different origins, so we must not pass auth
  // headers
  const logFileUrl = 'https://example.org/logs/build-output.txt'
  setAuthToken('foobar')

  getLogFile(logFileUrl, true)
  expect(axios.get).toHaveBeenCalledTimes(1)
  expect(axios.get).toHaveBeenCalledWith(logFileUrl, { headers: {} })
})

it('should pass additional request configs to axios', () => {
  Object.defineProperty(process.env, 'REACT_APP_ZUUL_API', {
    value: 'https://example.com/api/'
  })

  const logFileUrl = 'https://example.com/logs/build-output.txt'
  setAuthToken('foobar')

  getLogFile(logFileUrl, true, { transformResponse: [] })
  expect(axios.get).toHaveBeenCalledTimes(1)
  expect(axios.get).toHaveBeenCalledWith(logFileUrl, {
    headers: { Authorization: 'Bearer foobar' },
    transformResponse: [],
  })
})
