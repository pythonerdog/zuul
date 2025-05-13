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

"""buildset_event_table

Revision ID: 6c1582c1d08c
Revises: ac1dad8c9434
Create Date: 2024-03-25 12:28:58.885794

"""

# revision identifiers, used by Alembic.
revision = '6c1582c1d08c'
down_revision = 'ac1dad8c9434'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

BUILDSET_EVENT_TABLE = "zuul_buildset_event"
BUILDSET_TABLE = "zuul_buildset"


def upgrade(table_prefix=''):
    prefixed_buildset_event = table_prefix + BUILDSET_EVENT_TABLE
    prefixed_buildset = table_prefix + BUILDSET_TABLE

    op.create_table(
        prefixed_buildset_event,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("buildset_id", sa.Integer,
                  sa.ForeignKey(
                      f'{prefixed_buildset}.id',
                      name=f'{prefixed_buildset_event}_buildset_id_fkey',
                  )),
        sa.Column("event_time", sa.DateTime),
        sa.Column("event_type", sa.String(255)),
        sa.Column("description", sa.TEXT()),
    )
    op.create_index(
        f'{prefixed_buildset_event}_buildset_id_idx',
        prefixed_buildset_event,
        ['buildset_id'])


def downgrade():
    raise Exception("Downgrades not supported")
