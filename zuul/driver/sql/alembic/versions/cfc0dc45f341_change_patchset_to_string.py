"""Change patchset to string

Revision ID: cfc0dc45f341
Revises: ba4cdce9b18c
Create Date: 2018-01-09 16:44:31.506958

"""

# revision identifiers, used by Alembic.
revision = 'cfc0dc45f341'
down_revision = 'ba4cdce9b18c'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

BUILDSET_TABLE = 'zuul_buildset'

# Note: the following migration does not do what it was intended to do
# (change the column type to a string).  It was introduced with an
# error which instead caused the nullable flag to be set to true (even
# though it was already set), effectively making it a no-op.  To
# maintain compatibility with later versions of alembic, this has been
# updated to explicitly do now what it implicitly did then.  A later
# migration (19d3a3ebfe1d) corrects the error and changes the type.


def upgrade(table_prefix=''):
    op.alter_column(table_prefix + BUILDSET_TABLE,
                    'patchset',
                    nullable=True,
                    existing_nullable=True,
                    existing_type=sa.Integer)


def downgrade():
    raise Exception("Downgrades not supported")
