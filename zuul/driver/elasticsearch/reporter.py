# Copyright 2019 Red Hat, Inc.
# Copyright 2024 Acme Gating, LLC
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

import time
import logging

import voluptuous as v

from zuul.reporter import BaseReporter


class ElasticsearchReporter(BaseReporter):
    name = 'elasticsearch'
    log = logging.getLogger("zuul.ElasticsearchReporter")

    def __init__(self, driver, connection, config):
        super(ElasticsearchReporter, self).__init__(driver, connection, config)
        self.index = self.config.get('index', 'zuul')
        self.index_vars = self.config.get('index-vars')
        self.index_returned_vars = self.config.get('index-returned-vars')

    def report(self, item, phase1=True, phase2=True):
        """Create an entry into a database."""
        if not phase1:
            return
        docs = []
        index = '%s.%s-%s' % (self.index, item.manager.tenant.name,
                              time.strftime("%Y.%m.%d"))
        changes = [
            {
                "project": change.project.name,
                "change": getattr(change, 'number', None),
                "patchset": getattr(change, 'patchset', None),
                "ref": getattr(change, 'ref', ''),
                "oldrev": getattr(change, 'oldrev', ''),
                "newrev": getattr(change, 'newrev', ''),
                "branch": getattr(change, 'branch', ''),
                "ref_url": change.url,
            }
            for change in item.changes
        ]
        buildset_doc = {
            "uuid": item.current_build_set.uuid,
            "build_type": "buildset",
            "tenant": item.manager.tenant.name,
            "pipeline": item.manager.pipeline.name,
            "changes": changes,
            "project": item.changes[0].project.name,
            "change": getattr(item.changes[0], 'number', None),
            "patchset": getattr(item.changes[0], 'patchset', None),
            "ref": getattr(item.changes[0], 'ref', ''),
            "oldrev": getattr(item.changes[0], 'oldrev', ''),
            "newrev": getattr(item.changes[0], 'newrev', ''),
            "branch": getattr(item.changes[0], 'branch', ''),
            "zuul_ref": item.current_build_set.ref,
            "ref_url": item.changes[0].url,
            "result": item.current_build_set.result,
            "message": self._formatItemReport(item, with_jobs=False)
        }

        for job in item.getJobs():
            build = item.current_build_set.getBuild(job)
            if not build:
                continue
            # Ensure end_time is defined
            if not build.end_time:
                build.end_time = time.time()
            # Ensure start_time is defined
            if not build.start_time:
                build.start_time = build.end_time

            (result, url) = item.formatJobResult(job)

            # Manage to set time attributes in buildset
            start_time = int(build.start_time)
            end_time = int(build.end_time)
            if ('start_time' not in buildset_doc or
                    buildset_doc['start_time'] > start_time):
                buildset_doc['start_time'] = start_time
            if ('end_time' not in buildset_doc or
                    buildset_doc['end_time'] < end_time):
                buildset_doc['end_time'] = end_time
            buildset_doc['duration'] = (
                buildset_doc['end_time'] - buildset_doc['start_time'])

            change = item.getChangeForJob(build.job)
            change_doc = {
                "project": change.project.name,
                "change": getattr(change, 'number', None),
                "patchset": getattr(change, 'patchset', None),
                "ref": getattr(change, 'ref', ''),
                "oldrev": getattr(change, 'oldrev', ''),
                "newrev": getattr(change, 'newrev', ''),
                "branch": getattr(change, 'branch', ''),
                "ref_url": change.url,
            }

            build_doc = {
                "uuid": build.uuid,
                "change": change_doc,
                "build_type": "build",
                "buildset_uuid": buildset_doc['uuid'],
                "job_name": build.job.name,
                "result": result,
                "start_time": str(start_time),
                "end_time": str(end_time),
                "duration": end_time - start_time,
                "voting": build.job.voting,
                "log_url": url,
            }

            # Extends the build doc with some buildset info
            for attr in (
                    'tenant', 'pipeline', 'project', 'change', 'patchset',
                    'ref', 'oldrev', 'newrev', 'branch'):
                build_doc[attr] = buildset_doc[attr]

            if self.index_vars:
                build_doc['job_vars'] = job.variables

            if self.index_returned_vars:
                rdata = build.result_data.copy()
                rdata.pop('zuul', None)
                build_doc['job_returned_vars'] = rdata

            docs.append(build_doc)

        docs.append(buildset_doc)
        self.connection.add_docs(docs, index)


def getSchema():
    el_reporter = v.Schema(
        v.Any(
            None,
            {
                'index': str,
                'index-vars': bool,
                'index-returned-vars': bool
            }
        )
    )
    return el_reporter
