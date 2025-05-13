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

"""buildset_updated

Revision ID: c7467b642498
Revises: 4647def24b32
Create Date: 2022-05-28 16:21:50.035877

"""

# revision identifiers, used by Alembic.
revision = 'c7467b642498'
down_revision = '4647def24b32'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade(table_prefix=''):
    op.add_column(
        table_prefix + "zuul_buildset", sa.Column('updated', sa.DateTime))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE {buildset_table}
              SET updated=greatest(
                coalesce(first_build_start_time, '1970-01-01 00:00:00'),
                coalesce(last_build_end_time, '1970-01-01 00:00:00'),
                coalesce(event_timestamp, '1970-01-01 00:00:00'))
            """.format(buildset_table=table_prefix + "zuul_buildset")
        )
    )


def downgrade():
    raise Exception("Downgrades not supported")
