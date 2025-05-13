# Copyright 2022 BMW Group
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

"""add_build_event_table

Revision ID: 0ed5def089e2
Revises: c7467b642498
Create Date: 2022-12-12 12:08:20.882790

"""

# revision identifiers, used by Alembic.
revision = '0ed5def089e2'
down_revision = 'c7467b642498'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

BUILD_EVENT_TABLE = "zuul_build_event"
BUILD_TABLE = "zuul_build"


def upgrade(table_prefix=''):
    op.create_table(
        table_prefix + BUILD_EVENT_TABLE,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("build_id", sa.Integer,
                  sa.ForeignKey(table_prefix + BUILD_TABLE + ".id")),
        sa.Column("event_time", sa.DateTime),
        sa.Column("event_type", sa.String(255)),
        sa.Column("description", sa.TEXT()),
    )


def downgrade():
    raise Exception("Downgrades not supported")
