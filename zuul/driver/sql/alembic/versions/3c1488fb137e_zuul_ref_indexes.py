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

"""zuul_ref_indexes

Revision ID: 3c1488fb137e
Revises: d0a269345a22
Create Date: 2023-11-27 17:15:00.812075

"""

# revision identifiers, used by Alembic.
revision = '3c1488fb137e'
down_revision = 'd0a269345a22'
branch_labels = None
depends_on = None

from alembic import op

REF_TABLE = 'zuul_ref'


def upgrade(table_prefix=''):
    prefixed_ref = table_prefix + REF_TABLE

    op.create_index(f'{prefixed_ref}_project_idx',
                    prefixed_ref,
                    ['project'])
    op.create_index(f'{prefixed_ref}_ref_idx',
                    prefixed_ref,
                    ['ref'])
    op.create_index(f'{prefixed_ref}_branch_idx',
                    prefixed_ref,
                    ['branch'])
    # Change is already indexed
    op.create_index(f'{prefixed_ref}_patchset_idx',
                    prefixed_ref,
                    ['patchset'])
    op.create_index(f'{prefixed_ref}_oldrev_idx',
                    prefixed_ref,
                    ['oldrev'])
    op.create_index(f'{prefixed_ref}_newrev_idx',
                    prefixed_ref,
                    ['newrev'])

    # Drop the project_change index and rely on separate indexes that
    # may be merged by the dbms.
    op.drop_index(f'{prefixed_ref}_project_change_idx', prefixed_ref)


def downgrade():
    raise Exception("Downgrades not supported")
