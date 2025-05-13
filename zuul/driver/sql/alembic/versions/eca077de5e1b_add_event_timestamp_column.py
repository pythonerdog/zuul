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

"""add event timestamp column

Revision ID: eca077de5e1b
Revises: 40c49b6fc2e3
Create Date: 2022-01-03 13:52:37.262934

"""

# revision identifiers, used by Alembic.
revision = 'eca077de5e1b'
down_revision = '40c49b6fc2e3'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade(table_prefix=''):
    op.add_column(
        table_prefix + "zuul_buildset",
        sa.Column("event_timestamp", sa.DateTime, nullable=True)
    )


def downgrade():
    raise Exception("Downgrades not supported")
