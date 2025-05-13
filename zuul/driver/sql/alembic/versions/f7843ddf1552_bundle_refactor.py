# Copyright 2023 Acme Gating, LLC
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

"""bundle_refactor

Revision ID: f7843ddf1552
Revises: 151893067f91
Create Date: 2023-09-16 09:25:00.674820

"""

# revision identifiers, used by Alembic.
revision = 'f7843ddf1552'
down_revision = '151893067f91'
branch_labels = None
depends_on = None

import logging

from alembic import op
import sqlalchemy as sa


REF_TABLE = 'zuul_ref'
BUILD_TABLE = 'zuul_build'
BUILDSET_TABLE = 'zuul_buildset'
BUILDSET_REF_TABLE = 'zuul_buildset_ref'
ARTIFACT_TABLE = 'zuul_artifact'
BUILD_EVENT_TABLE = 'zuul_build_event'
PROVIDES_TABLE = 'zuul_provides'


def rename_index(connection, table, old, new):
    dialect_name = connection.engine.dialect.name
    if dialect_name in ('mysql', 'mariadb'):
        statement = f"""
            alter table {table}
            rename index {old}
            to {new}
        """
    elif dialect_name == 'postgresql':
        statement = f"""
            alter index {old}
            rename to {new}
        """
    else:
        raise Exception(f"Unsupported dialect {dialect_name}")
    connection.execute(sa.text(statement))


# This migration has an unusual structure.  We do quite a bit of work
# on temporary tables before we start replacing our real tables.
# Mysql doesn't support transactional DDL, but we can fairly easily
# undo our changes up to a certain point just by dropping our
# temporary tables.  To make life easier on operators in case there is
# a problem, if we encounter an error up to the point of no return, we
# will drop the tables and leave the db in the state it started.  If
# we encounter an error after that point, there is little we can do to
# recover, but hopefully we will have found errors prior to then, if
# any.

# Postgres has transactional DDL and the entire migraction is in a
# single transaction and is automatically rolled back.  We just no-op
# in that case.

# To accomodate this structure without having a giant try/except
# block, the migration is split into 2 functions, upgrade1() and
# upgrade2().

def upgrade1(connection, table_prefix):
    # This is the first part of the migration, which is recoverable in
    # mysql.
    prefixed_ref = table_prefix + REF_TABLE
    prefixed_build = table_prefix + BUILD_TABLE
    prefixed_build_new = table_prefix + BUILD_TABLE + '_new'
    prefixed_buildset = table_prefix + BUILDSET_TABLE
    prefixed_buildset_new = table_prefix + BUILDSET_TABLE + '_new'
    prefixed_buildset_ref = table_prefix + BUILDSET_REF_TABLE
    quote = connection.engine.dialect.identifier_preparer.quote
    dialect_name = connection.engine.dialect.name

    # This migration requires updates to existing rows in the
    # zuul_build and zuul_buildset tables.  In postgres, tables have a
    # fill factor which indicates how much space to leave in pages for
    # row updates.  With a high fill factor (the default is 100%)
    # large updates can be slow.  With a smaller fill factor, large
    # updates can bu much faster, at the cost of wasted space and
    # operational overhead.  The default of 100% makes sense for all
    # of our tables.  While the build and buildset tables do get some
    # row updates, they are not very frequent.  We would need a very
    # generous fill factor to be able to update all of the rows in the
    # build table quickly, and that wouldn't make sense for normal
    # operation.

    # Instead of adding columns and updating the table, we will
    # create new tables and populate them with inserts (which is
    # extremely fast), then remove the old tables and rename the new.

    # First, create zuul_buildset_new table.  This will later replace
    # the zuul_buildset table.  It includes some changes:

    # * We intentionally omit the zuul_ref column (in this case,
    #   referring to the old Z<sha> unique ids) because it is obsolete
    #   is obsolete.

    # * The length of the sha fields is lowered to 40.  This is so
    #   that in the zuul_ref table, we can make a unique index of
    #   several fields without hitting mysql's index length limit.
    #   We will mutate their values as we insert them here.
    op.create_table(
        prefixed_buildset_new,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('pipeline', sa.String(255)),
        sa.Column('message', sa.TEXT()),
        sa.Column('tenant', sa.String(255)),
        sa.Column('result', sa.String(255)),
        sa.Column('uuid', sa.String(36)),
        sa.Column('event_id', sa.String(255), nullable=True),
        sa.Column('event_timestamp', sa.DateTime, nullable=True),
        sa.Column('first_build_start_time', sa.DateTime, nullable=True),
        sa.Column('last_build_end_time', sa.DateTime, nullable=True),
        sa.Column('updated', sa.DateTime, nullable=True),
        # Columns we'll drop later, but need now in order to populate
        # zuul_ref.
        sa.Column('project', sa.String(255), nullable=False),
        sa.Column('ref', sa.String(255), nullable=False),
        sa.Column('ref_url', sa.String(255), nullable=False),
        sa.Column('change', sa.Integer, nullable=False),
        sa.Column('patchset', sa.String(40), nullable=False),
        sa.Column('oldrev', sa.String(40), nullable=False),
        sa.Column('newrev', sa.String(40), nullable=False),
        sa.Column('branch', sa.String(255), nullable=False),
    )

    # The postgres operator "is not distinct from" (equivalent to
    # mysql's <=>) is a non-indexable operator.  So that we can
    # actually use the unique index (and other indexes in the future)
    # make all of the ref-related columns non-null.  That means empty
    # strings for strings, and we'll use 0 for the change id.  This
    # lets us use the "=" operator and utilize the index for all
    # values.
    statement = f"""
        insert into {prefixed_buildset_new}
            select bs.id, bs.pipeline, bs.message,
                bs.tenant, bs.result, bs.uuid, bs.event_id, bs.event_timestamp,
                bs.first_build_start_time, bs.last_build_end_time, bs.updated,
                bs.project, coalesce(bs.ref, ''), coalesce(ref_url, ''),
                coalesce(bs.change, 0), coalesce(bs.patchset, ''),
                coalesce(bs.oldrev, ''), coalesce(bs.newrev, ''),
                coalesce(branch, '')
            from {prefixed_buildset} bs
    """
    connection.execute(sa.text(statement))

    # Create zuul_ref table.
    op.create_table(
        prefixed_ref,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('project', sa.String(255), nullable=False),
        sa.Column('ref', sa.String(255), nullable=False),
        sa.Column('ref_url', sa.String(255), nullable=False),
        sa.Column('change', sa.Integer, nullable=False),
        sa.Column('patchset', sa.String(40), nullable=False),
        sa.Column('oldrev', sa.String(40), nullable=False),
        sa.Column('newrev', sa.String(40), nullable=False),
        sa.Column('branch', sa.String(255), nullable=False),
    )

    # Copy data from buildset to ref.

    # We are going to have a unique index later on some columns, so we
    # use a "group by" clause here to remove duplicates.  We also may
    # have differing values for ref_url for the same refs (e.g.,
    # opendev switched gerrit server hostnames), so we arbitrarily
    # take the first ref_url for a given grouping.  It doesn't make
    # sense for branch to be different, but we do the same in order to
    # avoid any potential errors.
    statement = f"""
        insert into {prefixed_ref}
            (project, {quote('change')}, patchset,
             ref, ref_url, oldrev, newrev, branch)
        select
            bs.project, bs.change, bs.patchset,
            bs.ref, min(ref_url), bs.oldrev, bs.newrev, min(branch)
        from {prefixed_buildset_new} bs
        group by
            bs.project, bs.change, bs.patchset,
            bs.ref, bs.oldrev, bs.newrev
    """
    connection.execute(sa.text(statement))

    # Create our unique ref constraint; this includes as index that
    # will speed up populating the zuul_buildset_ref table.
    op.create_unique_constraint(
        f'{prefixed_ref}_unique',
        prefixed_ref,
        ['project', 'ref', 'change', 'patchset', 'oldrev', 'newrev'],
    )

    # Create replacement indexes for the obsolete indexes on the
    # buildset table.
    with op.batch_alter_table(prefixed_ref) as batch_op:
        batch_op.create_index(
            f'{prefixed_ref}_project_change_idx',
            ['project', 'change'])
        batch_op.create_index(
            f'{prefixed_ref}_change_idx',
            ['change'])

    # Add mapping table for buildset <-> ref

    # We will add foreign key constraints after populating the table.
    op.create_table(
        prefixed_buildset_ref,
        sa.Column('buildset_id', sa.Integer, nullable=False),
        sa.Column('ref_id', sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("buildset_id", "ref_id"),
    )

    # Populate buildset_ref table.  Ignore ref_url since we don't
    # include it in the unique index later.
    statement = f"""
        insert into {prefixed_buildset_ref}
        select {prefixed_buildset_new}.id, {prefixed_ref}.id
        from {prefixed_buildset_new} left join {prefixed_ref}
        on {prefixed_buildset_new}.project = {prefixed_ref}.project
        and {prefixed_buildset_new}.ref = {prefixed_ref}.ref
        and {prefixed_buildset_new}.change = {prefixed_ref}.change
        and {prefixed_buildset_new}.patchset = {prefixed_ref}.patchset
        and {prefixed_buildset_new}.oldrev = {prefixed_ref}.oldrev
        and {prefixed_buildset_new}.newrev = {prefixed_ref}.newrev
    """
    connection.execute(sa.text(statement))

    # Fix the sequence value since we wrote our own ids (postgres only)
    if dialect_name == 'postgresql':
        statement = f"""
            select setval(
                 '{prefixed_buildset_new}_id_seq',
                 COALESCE((SELECT MAX(id)+1 FROM {prefixed_buildset_new}), 1),
                 false)
        """
        connection.execute(sa.text(statement))

    # Now that the table is populated, add the FK indexes and
    # constraints to buildset_ref.
    op.create_index(
        f'{prefixed_buildset_ref}_buildset_id_idx',
        prefixed_buildset_ref, ['buildset_id'])
    op.create_index(
        f'{prefixed_buildset_ref}_ref_id_idx',
        prefixed_buildset_ref, ['ref_id'])

    # Alembic doesn't allow us to combine alter table operations, so
    # we do this manually.  It still takes the same total time in
    # mysql though.
    statement = f"""
        alter table {prefixed_buildset_ref}
        add constraint {prefixed_buildset_ref}_buildset_id_fkey
            foreign key(buildset_id)
            references {prefixed_buildset_new} (id),
        add constraint {prefixed_buildset_ref}_ref_id_fkey
            foreign key(ref_id)
            references {prefixed_ref} (id)
    """
    connection.execute(sa.text(statement))

    # Our goal below is to add the ref_id column to the build table
    # and populate it with a query.

    # Create the new build table.
    op.create_table(
        prefixed_build_new,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('buildset_id', sa.Integer),
        sa.Column('uuid', sa.String(36)),
        sa.Column('job_name', sa.String(255)),
        sa.Column('result', sa.String(255)),
        sa.Column('start_time', sa.DateTime),
        sa.Column('end_time', sa.DateTime),
        sa.Column('voting', sa.Boolean),
        sa.Column('log_url', sa.String(255)),
        sa.Column('error_detail', sa.TEXT()),
        sa.Column('final', sa.Boolean),
        sa.Column('held', sa.Boolean),
        sa.Column('nodeset', sa.String(255)),
        sa.Column('ref_id', sa.Integer),
    )

    # Populate it with existing values, but get the ref_id for the
    # build from the buildset_ref table (we know that currently a
    # buildset is associated with exactly one ref, so we can use that
    # ref to associate its builds).
    statement = f"""
        insert into {prefixed_build_new}
            select
                {prefixed_build}.id,
                {prefixed_build}.buildset_id,
                {prefixed_build}.uuid,
                {prefixed_build}.job_name,
                {prefixed_build}.result,
                {prefixed_build}.start_time,
                {prefixed_build}.end_time,
                {prefixed_build}.voting,
                {prefixed_build}.log_url,
                {prefixed_build}.error_detail,
                {prefixed_build}.final,
                {prefixed_build}.held,
                {prefixed_build}.nodeset,
                {prefixed_buildset_ref}.ref_id
            from {prefixed_build} left join {prefixed_buildset_ref}
              on {prefixed_build}.buildset_id =
                 {prefixed_buildset_ref}.buildset_id
    """
    connection.execute(sa.text(statement))

    # Fix the sequence value since we wrote our own ids (postgres only)
    if dialect_name == 'postgresql':
        statement = f"""
            select setval(
                 '{prefixed_build_new}_id_seq',
                 COALESCE((SELECT MAX(id)+1 FROM {prefixed_build_new}), 1),
                 false)
        """
        connection.execute(sa.text(statement))

    # Add the foreign key indexes and constraits to our new table
    # first, to make sure we can before we drop the old one.
    with op.batch_alter_table(prefixed_build_new) as batch_op:
        batch_op.create_index(
            f'{prefixed_build_new}_buildset_id_idx',
            ['buildset_id'])
        batch_op.create_index(
            f'{prefixed_build_new}_ref_id_idx',
            ['ref_id'])

    # Mysql is quite slow about adding FK constraints.  But we're
    # pretty sure the data are valid (one of these constraints is
    # identical to one on the buildset table, and the other should be
    # identical to one on the buildset_ref table).
    # Disable FK checks from this point forward.
    if dialect_name in ('mysql', 'mariadb'):
        connection.execute(sa.text("set foreign_key_checks = 0"))

    statement = f"""
        alter table {prefixed_build_new}
        add constraint {prefixed_build_new}_buildset_id_fkey
            foreign key(buildset_id)
            references {prefixed_buildset_new} (id),
        add constraint {prefixed_build_new}_ref_id_fkey
            foreign key(ref_id)
            references {prefixed_ref} (id)
    """
    connection.execute(sa.text(statement))

    # After this point we expect everything else to succeed and
    # we can no longer roll back in mysql without data loss.


def rollback(connection, table_prefix):
    # This is our homemade best-effort rollback for mysql.
    prefixed_ref = table_prefix + REF_TABLE
    prefixed_build_new = table_prefix + BUILD_TABLE + '_new'
    prefixed_buildset_new = table_prefix + BUILDSET_TABLE + '_new'
    prefixed_buildset_ref = table_prefix + BUILDSET_REF_TABLE
    dialect_name = connection.engine.dialect.name

    connection.execute(sa.text(
        f"drop table if exists {prefixed_ref}"))
    connection.execute(sa.text(
        f"drop table if exists {prefixed_build_new}"))
    connection.execute(sa.text(
        f"drop table if exists {prefixed_buildset_new}"))
    connection.execute(sa.text(
        f"drop table if exists {prefixed_buildset_ref}"))
    if dialect_name in ('mysql', 'mariadb'):
        connection.execute(sa.text("set foreign_key_checks = 1"))


def upgrade2(connection, table_prefix):
    # This is the second part of the migration, past the point of no
    # return for mysql.
    prefixed_ref = table_prefix + REF_TABLE
    prefixed_build = table_prefix + BUILD_TABLE
    prefixed_build_new = table_prefix + BUILD_TABLE + '_new'
    prefixed_buildset = table_prefix + BUILDSET_TABLE
    prefixed_buildset_new = table_prefix + BUILDSET_TABLE + '_new'
    prefixed_artifact = table_prefix + ARTIFACT_TABLE
    prefixed_build_event = table_prefix + BUILD_EVENT_TABLE
    prefixed_provides = table_prefix + PROVIDES_TABLE
    quote = connection.engine.dialect.identifier_preparer.quote
    dialect_name = connection.engine.dialect.name

    # Temporarily drop the FK constraints that reference the old build
    # table. (This conditional is why we're renaming all the indexes
    # and constraints to be consistent across different backends).
    if dialect_name in ('mysql', 'mariadb'):
        op.drop_constraint(table_prefix + 'zuul_artifact_ibfk_1',
                           prefixed_artifact, 'foreignkey')
        op.drop_constraint(table_prefix + 'zuul_build_event_ibfk_1',
                           prefixed_build_event, 'foreignkey')
        op.drop_constraint(table_prefix + 'zuul_provides_ibfk_1',
                           prefixed_provides, 'foreignkey')
    elif dialect_name == 'postgresql':
        op.drop_constraint(table_prefix + 'zuul_artifact_build_id_fkey',
                           prefixed_artifact)
        op.drop_constraint(table_prefix + 'zuul_build_event_build_id_fkey',
                           prefixed_build_event)
        op.drop_constraint(table_prefix + 'zuul_provides_build_id_fkey',
                           prefixed_provides)
    else:
        raise Exception(f"Unsupported dialect {dialect_name}")

    # Drop the old table
    op.drop_table(prefixed_build)

    # Rename the table
    op.rename_table(prefixed_build_new, prefixed_build)

    # Rename the sequence and primary key (postgres only)
    if dialect_name == 'postgresql':
        statement = f"""
            alter sequence {prefixed_build_new}_id_seq
            rename to {prefixed_build}_id_seq;
        """
        connection.execute(sa.text(statement))
        rename_index(connection, prefixed_build_new,
                     f'{prefixed_build_new}_pkey',
                     f'{prefixed_build}_pkey')

    # Replace the indexes
    with op.batch_alter_table(prefixed_build) as batch_op:
        # This used to be named job_name_buildset_id_idx, let's
        # upgrade to our new naming scheme
        batch_op.create_index(
            f'{prefixed_build}_job_name_buildset_id_idx',
            ['job_name', 'buildset_id'])
        # Previously named uuid_buildset_id_idx
        batch_op.create_index(
            f'{prefixed_build}_uuid_buildset_id_idx',
            ['uuid', 'buildset_id'])

    # Rename indexes
    rename_index(connection, prefixed_build,
                 f'{prefixed_build_new}_buildset_id_idx',
                 f'{prefixed_build}_buildset_id_idx')
    rename_index(connection, prefixed_build,
                 f'{prefixed_build_new}_ref_id_idx',
                 f'{prefixed_build}_ref_id_idx')

    # Mysql does not support renaming constraints, so we drop and
    # re-add them.  We added them earlier to confirm that there were
    # no errors before dropping the original table (though in mysql we
    # did so with checks disabled, but postgres was able to validate
    # them.  We could have skipped the earlier add for mysql, but this
    # keeps the code simpler and more consistent, and is still fast).
    if dialect_name in ('mysql', 'mariadb'):
        statement = f"""
        alter table {prefixed_build}
        drop foreign key {prefixed_build_new}_buildset_id_fkey,
        drop foreign key {prefixed_build_new}_ref_id_fkey,
        add constraint {prefixed_build}_buildset_id_fkey
            foreign key(buildset_id)
            references {prefixed_buildset_new} (id),
        add constraint {prefixed_build}_ref_id_fkey
            foreign key(ref_id)
            references {prefixed_ref} (id)
        """
    elif dialect_name == 'postgresql':
        statement = f"""
        alter table {prefixed_build}
        drop constraint {prefixed_build_new}_buildset_id_fkey,
        drop constraint {prefixed_build_new}_ref_id_fkey,
        add constraint {prefixed_build}_buildset_id_fkey
            foreign key(buildset_id)
            references {prefixed_buildset_new} (id),
        add constraint {prefixed_build}_ref_id_fkey
            foreign key(ref_id)
            references {prefixed_ref} (id)
        """
    else:
        raise Exception(f"Unsupported dialect {dialect_name}")
    connection.execute(sa.text(statement))

    # Re-add the referencing FK constraints
    op.create_foreign_key(
        f'{prefixed_artifact}_build_id_fkey',
        prefixed_artifact,
        prefixed_build,
        ['build_id'], ['id'])
    op.create_foreign_key(
        f'{prefixed_build_event}_build_id_fkey',
        prefixed_build_event,
        prefixed_build,
        ['build_id'], ['id'])
    op.create_foreign_key(
        f'{prefixed_provides}_build_id_fkey',
        prefixed_provides,
        prefixed_build,
        ['build_id'], ['id'])

    # Rename some indexes for a consistent naming scheme
    rename_index(connection, prefixed_artifact,
                 f'{table_prefix}artifact_build_id_idx',
                 f'{prefixed_artifact}_build_id_idx')
    rename_index(connection, prefixed_build_event,
                 f'{table_prefix}build_event_build_id_idx',
                 f'{prefixed_build_event}_build_id_idx')
    rename_index(connection, prefixed_provides,
                 f'{table_prefix}provides_build_id_idx',
                 f'{prefixed_provides}_build_id_idx')

    # Rename the buildset table
    op.drop_table(prefixed_buildset)
    op.rename_table(prefixed_buildset_new, prefixed_buildset)

    # Rename the sequence and primary key (postgres only)
    if dialect_name == 'postgresql':
        statement = f"""
            alter sequence {prefixed_buildset_new}_id_seq
            rename to {prefixed_buildset}_id_seq;
        """
        connection.execute(sa.text(statement))
        rename_index(connection, prefixed_build_new,
                     f'{prefixed_buildset_new}_pkey',
                     f'{prefixed_buildset}_pkey')

    # Drop the columns that are no longer used in one statement for
    # efficiency (alembic doesn't have a way to do this).
    statement = f"""alter table {prefixed_buildset}
        drop column project,
        drop column {quote('change')},
        drop column patchset,
        drop column ref,
        drop column ref_url,
        drop column oldrev,
        drop column newrev,
        drop column branch
    """
    connection.execute(sa.text(statement))

    # Replace the only remaining buildset index
    op.create_index(
        f'{prefixed_buildset}_uuid_idx',
        prefixed_buildset,
        ['uuid'])

    # Re-enable FK checks for mysql
    if dialect_name in ('mysql', 'mariadb'):
        connection.execute(sa.text("set foreign_key_checks = 1"))


def upgrade(table_prefix=''):
    # The actual upgrade method, simplified for exception/rollback
    # handling.
    connection = op.get_bind()
    dialect_name = connection.engine.dialect.name
    if dialect_name not in ('mysql', 'mariadb', 'postgresql'):
        raise Exception(f"Unsupported dialect {dialect_name}")

    log = logging.getLogger('zuul.SQLMigration')
    try:
        upgrade1(connection, table_prefix)
    except Exception:
        try:
            if dialect_name in ('mysql', 'mariadb'):
                log.error("Early error in schema migration, rolling back")
                rollback(connection, table_prefix)
        except Exception:
            log.exception("Error in migration rollback:")
        raise
    upgrade2(connection, table_prefix)


def downgrade():
    raise Exception("Downgrades not supported")
