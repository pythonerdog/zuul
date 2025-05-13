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

"""fix_branchless_refs

Revision ID: d0a269345a22
Revises: f7843ddf1552
Create Date: 2023-11-21 12:04:22.123186

"""

# revision identifiers, used by Alembic.
revision = 'd0a269345a22'
down_revision = 'f7843ddf1552'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


REF_TABLE = 'zuul_ref'


def upgrade(table_prefix=''):
    prefixed_ref = table_prefix + REF_TABLE
    statement = f"""
        update {prefixed_ref}
        set branch=substring(ref from 12)
        where branch='' and ref like 'refs/heads/%'
    """
    connection = op.get_bind()
    connection.execute(sa.text(statement))


def downgrade():
    raise Exception("Downgrades not supported")
