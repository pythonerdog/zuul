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

"""build_times

Revision ID: ac1dad8c9434
Revises: 3c1488fb137e
Create Date: 2023-10-31 15:27:40.014371

"""

# revision identifiers, used by Alembic.
revision = 'ac1dad8c9434'
down_revision = '3c1488fb137e'
branch_labels = None
depends_on = None

from alembic import op


BUILD_TABLE = 'zuul_build'
BUILDSET_TABLE = 'zuul_buildset'


def upgrade(table_prefix=''):
    prefixed_build = table_prefix + BUILD_TABLE
    prefixed_buildset = table_prefix + BUILDSET_TABLE
    op.create_index(
        f'{prefixed_build}_end_time_idx',
        prefixed_build, ['end_time'])
    op.create_index(
        f'{prefixed_buildset}_tenant_idx',
        prefixed_buildset, ['tenant'])


def downgrade():
    raise Exception("Downgrades not supported")
