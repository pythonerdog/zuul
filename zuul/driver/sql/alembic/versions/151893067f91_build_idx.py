# Copyright 2023 Acme Gating, LLC
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

"""build_idx

Revision ID: 151893067f91
Revises: 0ed5def089e2
Create Date: 2023-07-05 11:50:03.931815

"""

# revision identifiers, used by Alembic.
revision = '151893067f91'
down_revision = '0ed5def089e2'
branch_labels = None
depends_on = None

from alembic import op


def upgrade(table_prefix=''):
    # Create indexes like:
    # artifact_build_idx on zuul_artifact.build_id
    # This happens automatically on foreign keys in mysql but must be
    # done explicitly in postgres.
    for suffix in ['artifact',
                   'provides',
                   'build_event']:
        op.create_index(
            f'{table_prefix}{suffix}_build_id_idx',
            f'{table_prefix}zuul_{suffix}', ['build_id'])
    op.create_index(
        f'{table_prefix}build_buildset_id_idx',
        f'{table_prefix}zuul_build', ['buildset_id'])


def downgrade():
    raise Exception("Downgrades not supported")
