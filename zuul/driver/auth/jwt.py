# Copyright 2019 OpenStack Foundation
# Copyright 2019 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import math
import threading
import time
import jwt
import requests
from urllib.parse import urljoin

from zuul import exceptions
from zuul.driver import AuthenticatorInterface
from zuul.lib.config import any_to_bool


logger = logging.getLogger("zuul.auth.jwt")

# A few notes on differences between the OpenID Connect specification
# and OIDC as implemented by Microsoft, which necessitates several
# extra configuration options:
#
# 1) The issuer (iss) returned in the JWT is not the authority, but
# rather a URL referring to the AD instance, therefore authority must
# be specified separately.
# 2) The audience (aud) returned in the JWT is not the client_id, but
# rather a URL constructed from the client_id, therefore must also be
# specified separately.
# 3) By default, the JWT is simply a forwarded copy of a token from
# the Microsoft Graph service.  It is signed by the graph service and
# not the authority as requested, it therefore fails signature
# validation.  In order to cause the authority to generate its own
# token signed by the expected keys, we must create a new scope
# (api://.../zuul) and request that scope with the token.
# 4) The userinfo service referred to by the JWT is the Microsoft
# Graph service, which means that once our token is signed by the
# Microsoft login keys (see item #3) the graph service is then unable
# to validate the token.  Therefore we must configure the javascript
# oidc library not to request userinfo and rely only on what is
# supplied in the token.


class JWTAuthenticator(AuthenticatorInterface):
    """The base class for JWT-based authentication."""

    def __init__(self, **conf):
        # Common configuration for all authenticators
        self.uid_claim = conf.get('uid_claim', 'sub')
        self.issuer_id = conf.get('issuer_id')
        self.authority = conf.get('authority', self.issuer_id)
        self.client_id = conf.get('client_id')
        self.audience = conf.get('audience', self.client_id)
        self.realm = conf.get('realm')
        self.allow_authz_override = any_to_bool(
            conf.get('allow_authz_override', False))
        try:
            self.skew = int(conf.get('skew', 0))
        except Exception:
            raise ValueError(
                'skew must be an integer, got %s' % conf.get('skew'))
        try:
            self.max_validity_time = float(conf.get('max_validity_time',
                                                    math.inf))
        except ValueError:
            raise ValueError('"max_validity_time" must be a numerical value')

    def get_capabilities(self):
        return {
            self.realm: {
                'authority': self.authority,
                'client_id': self.client_id,
                'type': 'JWT',
                'driver': getattr(self, 'name', 'N/A'),
            }
        }

    def _decode(self, rawToken):
        raise NotImplementedError

    def decodeToken(self, rawToken):
        """Verify the raw token and return the decoded dictionary of claims"""
        try:
            decoded = self._decode(rawToken)
        except jwt.exceptions.InvalidSignatureError:
            raise exceptions.AuthTokenInvalidSignatureException(
                realm=self.realm)
        except jwt.exceptions.DecodeError:
            raise exceptions.AuthTokenUndecodedException(
                realm=self.realm)
        except jwt.exceptions.ExpiredSignatureError:
            raise exceptions.TokenExpiredError(
                realm=self.realm)
        except jwt.exceptions.InvalidIssuerError:
            raise exceptions.IssuerUnknownError(
                realm=self.realm)
        except jwt.exceptions.InvalidAudienceError:
            raise exceptions.IncorrectAudienceError(
                realm=self.realm)
        except Exception as e:
            raise exceptions.AuthTokenUnauthorizedException(
                realm=self.realm,
                msg=e)
        # Missing claim tests
        if not all(x in decoded for x in ['aud', 'iss', 'exp', 'sub']):
            raise exceptions.MissingClaimError(realm=self.realm)
        if self.max_validity_time < math.inf and 'iat' not in decoded:
            raise exceptions.MissingClaimError(
                msg='Missing "iat" claim',
                realm=self.realm)
        if self.uid_claim not in decoded:
            raise exceptions.MissingUIDClaimError(realm=self.realm)
        # Time related tests
        expires = decoded.get('exp', 0)
        issued_at = decoded.get('iat', 0)
        now = time.time()
        if issued_at + self.skew > now:
            raise exceptions.AuthTokenUnauthorizedException(
                msg='"iat" claim set in the future',
                realm=self.realm
            )
        if now - issued_at > self.max_validity_time:
            raise exceptions.TokenExpiredError(
                msg='Token was issued too long ago',
                realm=self.realm)
        if expires + self.skew < now:
            raise exceptions.TokenExpiredError(realm=self.realm)
        # Zuul-specific claims tests
        zuul_claims = decoded.get('zuul', {})
        admin_tenants = zuul_claims.get('admin', [])
        if not isinstance(admin_tenants, list):
            raise exceptions.IncorrectZuulAdminClaimError(realm=self.realm)
        if admin_tenants and not self.allow_authz_override:
            msg = ('Issuer "%s" attempt to override User "%s" '
                   'authorization denied')
            logger.info(msg % (decoded['iss'], decoded[self.uid_claim]))
            logger.debug('%r' % admin_tenants)
            raise exceptions.UnauthorizedZuulAdminClaimError(
                realm=self.realm)
        if admin_tenants and self.allow_authz_override:
            msg = ('Issuer "%s" attempt to override User "%s" '
                   'authorization granted')
            logger.info(msg % (decoded['iss'], decoded[self.uid_claim]))
            logger.debug('%r' % admin_tenants)
        return decoded

    def authenticate(self, rawToken):
        decoded = self.decodeToken(rawToken)
        # inject the special authenticator-specific uid
        decoded['__zuul_uid_claim'] = decoded[self.uid_claim]
        return decoded


class HS256Authenticator(JWTAuthenticator):
    """JWT authentication using the HS256 algorithm.

    Requires a shared secret between Zuul and the identity provider."""

    name = algorithm = 'HS256'

    def __init__(self, **conf):
        super(HS256Authenticator, self).__init__(**conf)
        self.secret = conf.get('secret')

    def _decode(self, rawToken):
        return jwt.decode(rawToken, self.secret, issuer=self.issuer_id,
                          audience=self.audience,
                          algorithms=[self.algorithm])


class RS256Authenticator(JWTAuthenticator):
    """JWT authentication using the RS256 algorithm.

    Requires a copy of the public key of the identity provider."""

    name = algorithm = 'RS256'

    def __init__(self, **conf):
        super(RS256Authenticator, self).__init__(**conf)
        with open(conf.get('public_key')) as pk:
            self.public_key = pk.read()

    def _decode(self, rawToken):
        return jwt.decode(rawToken, self.public_key, issuer=self.issuer_id,
                          audience=self.audience,
                          algorithms=[self.algorithm])


class OpenIDConnectAuthenticator(JWTAuthenticator):
    """JWT authentication using an OpenIDConnect provider.

    If the optional 'keys_url' parameter is not specified, the authenticator
    will attempt to determine it via the well-known configuration URI as
    described in
    https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderConfig"""  # noqa

    # default algorithm, TODO: should this be a config param?
    algorithm = 'RS256'
    name = 'OpenIDConnect'

    def __init__(self, **conf):
        super(OpenIDConnectAuthenticator, self).__init__(**conf)
        self.keys_url = conf.get('keys_url', None)
        self.scope = conf.get('scope', 'openid profile')
        self.load_user_info = any_to_bool(
            conf.get('load_user_info', True))
        self._init_lock = threading.Lock()
        self._client = None

    def get_client(self):
        if self._client is not None:
            return self._client
        with self._init_lock:
            if self._client is not None:
                return self._client
            keys_url = self.keys_url
            if keys_url is None:
                well_known = self.get_well_known_config()
                keys_url = well_known.get('jwks_uri', None)
            if keys_url is None:
                msg = 'Invalid OpenID configuration: "jwks_uri" not found'
                logger.error(msg)
                raise exceptions.JWKSException(
                    realm=self.realm,
                    msg=msg)
            self._client = jwt.PyJWKClient(keys_url)
            return self._client

    def get_key(self, key_id):
        # This has its own exception handler
        client = self.get_client()
        try:
            signing_key = client.get_signing_key(kid=key_id)
        except Exception as e:
            msg = 'Could not fetch Identity Provider keys at %s: %s'
            logger.error(msg % (client.uri, e))
            raise exceptions.JWKSException(
                realm=self.realm,
                msg='There was an error while fetching '
                    'keys for Identity Provider, check logs for details')
        algorithm = signing_key._jwk_data.get("alg", None) or self.algorithm
        key = signing_key.key
        return key, algorithm

    def get_well_known_config(self):
        issuer = self.issuer_id
        if not issuer.endswith('/'):
            issuer += '/'
        well_known_uri = urljoin(issuer,
                                 '.well-known/openid-configuration')
        try:
            return requests.get(well_known_uri).json()
        except Exception as e:
            msg = 'Could not fetch OpenID configuration at %s: %s'
            logger.error(msg % (well_known_uri, e))
            raise exceptions.JWKSException(
                realm=self.realm,
                msg='There was an error while fetching '
                    'OpenID configuration, check logs for details')

    def get_capabilities(self):
        d = super(OpenIDConnectAuthenticator, self).get_capabilities()
        d[self.realm]['scope'] = self.scope
        d[self.realm]['load_user_info'] = self.load_user_info
        return d

    def _decode(self, rawToken):
        unverified_headers = jwt.get_unverified_header(rawToken)
        key_id = unverified_headers.get('kid', None)
        if key_id is None:
            raise exceptions.JWKSException(
                self.realm, 'No key ID in token header')
        key, algorithm = self.get_key(key_id)
        return jwt.decode(rawToken, key, issuer=self.issuer_id,
                          audience=self.audience,
                          algorithms=[algorithm])


AUTHENTICATORS = {
    'HS256': HS256Authenticator,
    'RS256': RS256Authenticator,
    'RS256withJWKS': OpenIDConnectAuthenticator,
    'OpenIDConnect': OpenIDConnectAuthenticator,
}


def get_authenticator_by_name(name):
    if name == 'RS256withJWKS':
        logger.info(
            'Driver "%s" is deprecated, please use "OpenIDConnect" instead')
    return AUTHENTICATORS[name]
