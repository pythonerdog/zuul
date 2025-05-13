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

"""merge_conflict_rename

Revision ID: 4647def24b32
Revises: c57e9e76b812
Create Date: 2022-02-24 14:56:52.597907

"""

# revision identifiers, used by Alembic.
revision = '4647def24b32'
down_revision = 'c57e9e76b812'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

BUILDSET_TABLE = 'zuul_buildset'


def upgrade(table_prefix=''):
    buildset = sa.table(table_prefix + BUILDSET_TABLE, sa.column('result'))
    op.execute(buildset.update().
               where(buildset.c.result ==
                     op.inline_literal('MERGER_FAILURE')).
               values({'result': op.inline_literal('MERGE_CONFLICT')}))


def downgrade():
    raise Exception("Downgrades not supported")
