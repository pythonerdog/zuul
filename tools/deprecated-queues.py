#!/usr/bin/env python3
# Copyright 2022 Acme Gating, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import requests


def main():
    parser = argparse.ArgumentParser(
        description="Find where a project declares a queue")
    parser.add_argument("url", help="Zuul URL")
    parser.add_argument("tenant", help="Zuul tenant name")
    parser.add_argument("--verbose", help="Display progress",
                        action='store_true')
    args = parser.parse_args()

    projects = requests.get(
        f'{args.url}/api/tenant/{args.tenant}/projects',
    ).json()

    pipeline_contexts = set()
    for tenant_project in projects:
        if args.verbose:
            print(f"Checking {tenant_project['name']}")
        project = requests.get(
            f"{args.url}/api/tenant/{args.tenant}/project/"
            f"{tenant_project['name']}",
        ).json()

        for config in project['configs']:
            for pipeline in config['pipelines']:
                if pipeline['queue_name']:
                    pipeline_contexts.add(repr(config['source_context']))

    if pipeline_contexts:
        print("The following project-pipeline stanzas define a queue.")
        print("This syntax is deprecated and queue definitions should")
        print("be moved to the project level.")
        print("See https://zuul-ci.org/docs/zuul/latest/"
              "releasenotes.html#relnotes-4-1-0-deprecation-notes")
        for c in pipeline_contexts:
            print(c)
    else:
        print("Good, no project-pipeline queue definitions found.")


if __name__ == '__main__':
    main()
