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

"""buildset_start_end

Revision ID: c57e9e76b812
Revises: eca077de5e1b
Create Date: 2022-02-15 08:33:39.238458

"""

# revision identifiers, used by Alembic.
revision = 'c57e9e76b812'
down_revision = 'eca077de5e1b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade(table_prefix=''):
    op.add_column(
        table_prefix + "zuul_buildset",
        sa.Column("first_build_start_time", sa.DateTime, nullable=True),
    )
    op.add_column(
        table_prefix + "zuul_buildset",
        sa.Column("last_build_end_time", sa.DateTime, nullable=True)
    )


def downgrade():
    raise Exception("Downgrades not supported")
