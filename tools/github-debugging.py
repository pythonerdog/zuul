#!/usr/bin/env python3

import logging
from collections import UserDict

from zuul.driver.github.githubconnection import GithubConnection
from zuul.driver.github import GithubDriver
from zuul.model import Change
from zuul.zk.change_cache import ChangeKey

# This is a template with boilerplate code for debugging github issues

# TODO: for real use override the following variables
server = 'github.com'
api_token = 'xxxx'
appid = 2
appkey = '/opt/project/appkey'

org = 'example'
repo = 'sandbox'
pull_nr = 8


class DummyChangeCache(UserDict):

    def updateChangeWithRetry(self, key, change, update_func, retry_count=5):
        update_func(change)
        self[key] = change
        return change


def configure_logging(context):
    stream_handler = logging.StreamHandler()
    logger = logging.getLogger(context)
    logger.addHandler(stream_handler)
    logger.setLevel(logging.DEBUG)


# uncomment for more logging
# configure_logging('urllib3')
# configure_logging('github3')
# configure_logging('cachecontrol')


# This is all that's needed for getting a usable github connection
def create_connection(server, api_token):
    driver = GithubDriver()
    connection_config = {
        'server': server,
        'api_token': api_token,
    }
    conn = GithubConnection(driver, 'github', connection_config)
    conn._github_client_manager.initialize()
    conn._change_cache = DummyChangeCache()
    return conn


def create_connection_app(server, appid, appkey):
    driver = GithubDriver()
    connection_config = {
        'server': server,
        'app_id': appid,
        'app_key': appkey,
    }
    conn = GithubConnection(driver, 'github', connection_config)
    conn._github_client_manager.initialize()
    conn._change_cache = DummyChangeCache()
    return conn


def get_change(connection: GithubConnection,
               org: str,
               repo: str,
               pull: int) -> Change:
    project_name = f"{org}/{repo}"
    github = connection.getGithubClient(project_name)
    pr = github.pull_request(org, repo, pull)
    sha = pr.head.sha
    change_key = ChangeKey('github', project_name, 'PullRequest', pull, sha)
    return conn._getChange(change_key, refresh=True)


# create github connection with api token
conn = create_connection(server, api_token)

# create github connection with app key
# conn = create_connection_app(server, appid, appkey)


# Now we can do anything we want with the connection, e.g. check canMerge for
# a pull request.
change = get_change(conn, org, repo, pull_nr)

print(conn.canMerge(change, {'cc/gate2'}))


# Or just use the github object.
# github = conn.getGithubClient()
#
# repository = github.repository(org, repo)
# print(repository.as_dict())
