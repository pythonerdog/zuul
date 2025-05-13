# Copyright 2021-2023 Acme Gating, LLC
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

import difflib
import os
import re
import subprocess

from zuul.driver.sql import SQLDriver
from zuul.zk import ZooKeeperClient
from tests.base import (
    BaseTestCase,
    MySQLSchemaFixture,
    PostgresqlSchemaFixture,
    ZOOKEEPER_SESSION_TIMEOUT,
)

import sqlalchemy
import testtools


class DBBaseTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.setupZK()

        self.zk_client = ZooKeeperClient(
            self.zk_chroot_fixture.zk_hosts,
            tls_cert=self.zk_chroot_fixture.zookeeper_cert,
            tls_key=self.zk_chroot_fixture.zookeeper_key,
            tls_ca=self.zk_chroot_fixture.zookeeper_ca,
            timeout=ZOOKEEPER_SESSION_TIMEOUT,
        )
        self.addCleanup(self.zk_client.disconnect)
        self.zk_client.connect()


class TestMysqlDatabase(DBBaseTestCase):
    def setUp(self):
        super().setUp()

        f = MySQLSchemaFixture(self.id(), self.random_databases,
                               self.delete_databases)
        self.useFixture(f)

        config = dict(dburi=f.dburi)
        driver = SQLDriver()
        self.connection = driver.getConnection('database', config)
        self.connection.onLoad(self.zk_client)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        self.connection.onStop()

    def compareMysql(self, alembic_text, sqlalchemy_text):
        alembic_lines = alembic_text.split('\n')
        sqlalchemy_lines = sqlalchemy_text.split('\n')
        self.assertEqual(len(alembic_lines), len(sqlalchemy_lines))
        alembic_constraints = []
        sqlalchemy_constraints = []
        for i in range(len(alembic_lines)):
            if alembic_lines[i].startswith("  `"):
                # Column
                self.assertEqual(alembic_lines[i], sqlalchemy_lines[i])
            elif alembic_lines[i].startswith("  "):
                # Constraints can be unordered
                # strip trailing commas since the last line omits it
                alembic_constraints.append(
                    re.sub(',$', '', alembic_lines[i]))
                sqlalchemy_constraints.append(
                    re.sub(',$', '', sqlalchemy_lines[i]))
            else:
                self.assertEqual(alembic_lines[i], sqlalchemy_lines[i])
        alembic_constraints.sort()
        sqlalchemy_constraints.sort()
        self.assertEqual(alembic_constraints, sqlalchemy_constraints)

    def test_migration(self):
        # Test that SQLAlchemy create_all produces the same output as
        # a full migration run.
        sqlalchemy_tables = {}
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("set foreign_key_checks=0")
            for table in connection.exec_driver_sql("show tables"):
                table = table[0]
                sqlalchemy_tables[table] = connection.exec_driver_sql(
                    f"show create table {table}").one()[1]
                connection.exec_driver_sql(f"drop table {table}")
            connection.exec_driver_sql("set foreign_key_checks=1")

        self.connection.force_migrations = True
        self.connection.onLoad(self.zk_client)
        with self.connection.engine.begin() as connection:
            for table in connection.exec_driver_sql("show tables"):
                table = table[0]
                create = connection.exec_driver_sql(
                    f"show create table {table}").one()[1]
                self.compareMysql(create, sqlalchemy_tables[table])

    def test_migration_4647def24b32(self):
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("set foreign_key_checks=0")
            for table in connection.exec_driver_sql("show tables"):
                table = table[0]
                connection.exec_driver_sql(f"drop table {table}")
            connection.exec_driver_sql("set foreign_key_checks=1")

        self.connection.force_migrations = True
        self.connection._migrate('c57e9e76b812')
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql(
                "insert into zuul_buildset (project, result) "
                "values ('org/project', 'SUCCESS')")
            connection.exec_driver_sql(
                "insert into zuul_buildset (project, result) "
                "values ('org/project', 'MERGER_FAILURE')")
            results = [r[0] for r in connection.exec_driver_sql(
                "select result from zuul_buildset")]
            self.assertEqual(results, ['SUCCESS', 'MERGER_FAILURE'])

        self.connection._migrate()
        with self.connection.engine.begin() as connection:
            results = [r[0] for r in connection.exec_driver_sql(
                "select result from zuul_buildset")]
            self.assertEqual(results, ['SUCCESS', 'MERGE_CONFLICT'])

    def test_migration_c7467b642498(self):
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("set foreign_key_checks=0")
            for table in connection.exec_driver_sql("show tables"):
                table = table[0]
                connection.exec_driver_sql(f"drop table {table}")
            connection.exec_driver_sql("set foreign_key_checks=1")

        self.connection.force_migrations = True
        self.connection._migrate('4647def24b32')
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql(
                "insert into zuul_buildset (project, result) "
                "values ('org/project', 'SUCCESS')")
            connection.exec_driver_sql(
                "insert into zuul_buildset "
                "(project, result, first_build_start_time) "
                "values ('org/project', 'SUCCESS', '2022-05-01 12:34:56')")
            connection.exec_driver_sql(
                "insert into zuul_buildset "
                "(project, result, last_build_end_time) "
                "values ('org/project', 'SUCCESS', '2022-05-02 12:34:56')")
            connection.exec_driver_sql(
                "insert into zuul_buildset "
                "(project, result, event_timestamp) "
                "values ('org/project', 'SUCCESS', '2022-05-03 12:34:56')")
            connection.exec_driver_sql(
                "insert into zuul_buildset (project, result, "
                "first_build_start_time, "
                "last_build_end_time, "
                "event_timestamp)"
                "values ('org/project', 'SUCCESS', "
                "'2022-05-11 12:34:56', "
                "'2022-05-12 12:34:56', "
                "'2022-05-13 12:34:56')")

        self.connection._migrate()
        with self.connection.engine.begin() as connection:
            results = [str(r[0]) for r in connection.exec_driver_sql(
                "select updated from zuul_buildset")]
            self.assertEqual(results,
                             ['1970-01-01 00:00:00',
                              '2022-05-01 12:34:56',
                              '2022-05-02 12:34:56',
                              '2022-05-03 12:34:56',
                              '2022-05-13 12:34:56'])

    def test_migration_f7843ddf1552(self):
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("set foreign_key_checks=0")
            for table in connection.exec_driver_sql("show tables"):
                table = table[0]
                connection.exec_driver_sql(f"drop table {table}")
            connection.exec_driver_sql("set foreign_key_checks=1")

        self.connection.force_migrations = True
        self.connection._migrate('151893067f91')
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("""
            insert into zuul_buildset
            (id, uuid, zuul_ref, project, `change`, patchset, ref,
             ref_url, oldrev, newrev, branch)
            values
            (1, "bsuuid1", "Z1", "project1",
            1, "1",
            "refs/changes/1",
             "http://project1/1",
            "2d48fe5afe0bc7785294b28e9e96a6c622945b9d",
            "8a938aff20d691d1b9a9f461c6375f0c45acd305",
            "master"),
            (2, "bsuuid2", "Z2", "project1",
            2, "ee743613ce5b3aee11d12e91e932d7876bc0b40c",
            "refs/changes/2",
             "http://project1/2",
            "bd11c4ff79245ae555418e19840ce4752e48ea38",
            "d1ffc204e4b4955f2a47e7e37618fcf13bb1b9fd",
            "stable"),
            (3, "bsuuid3", "Z3", "project2", NULL, NULL, "refs/tags/foo",
             "http://project3",
            "a6cf0e07e9e2964a810196f764fc4ac766742568",
            "1a226acbd022968914574fdeb467b78bc5bfcc77",
            NULL)
            """)
            connection.exec_driver_sql("""
            insert into zuul_build
            (id, buildset_id, uuid, job_name, result)
            values
            (1, 1, "builduuid1", "job1", "RESULT1"),
            (2, 1, "builduuid2", "job2", "RESULT2"),
            (3, 2, "builduuid3", "job1", "RESULT3"),
            (4, 2, "builduuid4", "job2", "RESULT4"),
            (5, 3, "builduuid5", "job3", "RESULT5"),
            (6, 3, "builduuid6", "job4", "RESULT6")
            """)

        self.connection._migrate()
        with self.connection.engine.begin() as connection:
            results = [r for r in connection.exec_driver_sql(
                "select b.id, r.ref from zuul_build b join zuul_ref r "
                "on b.ref_id=r.id order by b.id")]
            self.assertEqual(results, [
                (1, 'refs/changes/1'),
                (2, 'refs/changes/1'),
                (3, 'refs/changes/2'),
                (4, 'refs/changes/2'),
                (5, 'refs/tags/foo'),
                (6, 'refs/tags/foo'),
            ])
            results = [r for r in connection.exec_driver_sql(
                "select bs.uuid, r.ref "
                "from zuul_buildset bs, zuul_buildset_ref t, zuul_ref r "
                "where bs.id = t.buildset_id and r.id = t.ref_id "
                "order by bs.uuid")]
            self.assertEqual(results, [
                ('bsuuid1', 'refs/changes/1'),
                ('bsuuid2', 'refs/changes/2'),
                ('bsuuid3', 'refs/tags/foo'),
            ])

    def test_migration_f7843ddf1552_failure(self):
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("set foreign_key_checks=0")
            for table in connection.exec_driver_sql("show tables"):
                table = table[0]
                connection.exec_driver_sql(f"drop table {table}")
            connection.exec_driver_sql("set foreign_key_checks=1")

        self.connection.force_migrations = True
        self.connection._migrate('151893067f91')
        # This test is identical to the one above, except the patchset
        # sha for the first buildset row is too long to fit in the
        # column (it's lengith is double).  The insert here is fine,
        # but that will cause the migration to fail.
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("""
            insert into zuul_buildset
            (id, uuid, zuul_ref, project, `change`, patchset, ref,
             ref_url, oldrev, newrev, branch)
            values
            (1, "bsuuid1", "Z1", "project1",
            1, "1",
            "refs/changes/1",
             "http://project1/1",
            "2d48fe5afe0bc7785294b28e9e96a6c622945b9d"
            "2d48fe5afe0bc7785294b28e9e96a6c622945b9d",
            "8a938aff20d691d1b9a9f461c6375f0c45acd305",
            "master"),
            (2, "bsuuid2", "Z2", "project1",
            2, "ee743613ce5b3aee11d12e91e932d7876bc0b40c",
            "refs/changes/2",
             "http://project1/2",
            "bd11c4ff79245ae555418e19840ce4752e48ea38",
            "d1ffc204e4b4955f2a47e7e37618fcf13bb1b9fd",
            "stable"),
            (3, "bsuuid3", "Z3", "project2", NULL, NULL, "refs/tags/foo",
             "http://project3",
            "a6cf0e07e9e2964a810196f764fc4ac766742568",
            "1a226acbd022968914574fdeb467b78bc5bfcc77",
            NULL)
            """)
            connection.exec_driver_sql("""
            insert into zuul_build
            (id, buildset_id, uuid, job_name, result)
            values
            (1, 1, "builduuid1", "job1", "RESULT1"),
            (2, 1, "builduuid2", "job2", "RESULT2"),
            (3, 2, "builduuid3", "job1", "RESULT3"),
            (4, 2, "builduuid4", "job2", "RESULT4"),
            (5, 3, "builduuid5", "job3", "RESULT5"),
            (6, 3, "builduuid6", "job4", "RESULT6")
            """)

        with testtools.ExpectedException(sqlalchemy.exc.DataError):
            self.connection._migrate()

        with self.connection.engine.begin() as connection:
            tables = [r[0] for r in connection.exec_driver_sql(
                "show tables")]
            # Make sure we rolled back the buildset_new table creation
            self.assertNotIn('zuul_buildset_new', tables)
            self.assertIn('zuul_buildset', tables)

    def test_migration_d0a269345a22(self):
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("set foreign_key_checks=0")
            for table in connection.exec_driver_sql("show tables"):
                table = table[0]
                connection.exec_driver_sql(f"drop table {table}")
            connection.exec_driver_sql("set foreign_key_checks=1")

        self.connection.force_migrations = True
        self.connection._migrate('f7843ddf1552')
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("""
            insert into zuul_ref
            (id, project, ref, ref_url, `change`,
            patchset, oldrev, newrev, branch)
            values
            (473951, 'openstack/neutron', 'refs/heads/master',
            'https://git.openstack.org/cgit/openstack/neutron/commit/?id=None',
            0, '', '', '', ''),
            (473958, 'openstack/neutron', 'refs/heads/master',
            'https://git.openstack.org/cgit/openstack/neutron/commit/'
            '?id=fd024ac468456561918e02d32f55eabada102fd3',
            0, '',
            '0017b625ddb64cb3f383e1a4b7f20b7a62153705',
            'fd024ac468456561918e02d32f55eabada102fd3',
            ''),
            (481941, 'openstack/neutron', 'refs/heads/stable/zed',
            'https://opendev.org/openstack/neutron/commit/'
            'd6ee668cc32725cb7d15d2e08fdb50a761f91fe4',
            0, '',
            'fdba20b27a1b97459db1e83f9b235149fe7fd1f7',
            'd6ee668cc32725cb7d15d2e08fdb50a761f91fe4',
            'stable/zed');
            """)
        self.connection._migrate()
        with self.connection.engine.begin() as connection:
            results = [r for r in connection.exec_driver_sql(
                "select id, ref, branch from zuul_ref order by id")]
            self.assertEqual(results, [
                (473951, 'refs/heads/master', 'master'),
                (473958, 'refs/heads/master', 'master'),
                (481941, 'refs/heads/stable/zed', 'stable/zed'),
            ])

    def test_buildsets(self):
        tenant = 'tenant1',
        buildset_uuid = 'deadbeef'
        change = 1234

        # Create the buildset entry (driver-internal interface)
        with self.connection.getSession() as db:
            bs = db.createBuildSet(
                uuid=buildset_uuid,
                tenant=tenant,
                pipeline='check',
                event_id='eventid',
            )
            ref = db.getOrCreateRef(
                project='project',
                change=change,
                patchset='1',
                ref='',
                oldrev='',
                newrev='',
                branch='master',
                ref_url='http://example.com/1234',
            )
            bs.refs.append(ref)

        # Verify that worked using the driver-external interface
        self.assertEqual(len(self.connection.getBuildsets()), 1)
        self.assertEqual(self.connection.getBuildsets()[0].uuid, buildset_uuid)

        # Update the buildset using the internal interface
        with self.connection.getSession() as db:
            db_buildset = db.getBuildset(tenant=tenant, uuid=buildset_uuid)
            self.assertEqual(db_buildset.refs[0].change, change)
            db_buildset.result = 'SUCCESS'

        # Verify that worked
        db_buildset = self.connection.getBuildset(
            tenant=tenant, uuid=buildset_uuid)
        self.assertEqual(db_buildset.result, 'SUCCESS')

    def test_sanitize_subtring_query(self):
        session = self.connection.getSession()
        self.assertEqual(None, session._sanitizeSubstringQuery(None))
        self.assertEqual(
            "job-name", session._sanitizeSubstringQuery("job-name"))
        self.assertEqual(
            "$%job-$%name$%", session._sanitizeSubstringQuery("%job-%name%"))
        self.assertEqual(
            "job$_-$%name$%", session._sanitizeSubstringQuery("job_-%name%"))
        self.assertEqual(
            "job$_-$%name$%", session._sanitizeSubstringQuery("job_-%name%"))
        self.assertEqual(
            "$$$%job$_-$%name$%",
            session._sanitizeSubstringQuery("$%job_-%name%"))

    def test_fuzzy_filter_op(self):
        col = sqlalchemy.Column("job_name")
        session = self.connection.getSession()

        filter = session._getFuzzyFilterOp(col, "job-name")
        self.assertEqual(type(col == "foo"), type(filter))
        self.assertEqual("job-name", filter.right.value)

        filter = session._getFuzzyFilterOp(col, "job%name")
        self.assertEqual(type(col == "foo"), type(filter))
        self.assertEqual("job%name", filter.right.value)

        filter = session._getFuzzyFilterOp(col, "job$name")
        self.assertEqual(type(col == "foo"), type(filter))
        self.assertEqual("job$name", filter.right.value)

        filter = session._getFuzzyFilterOp(col, "job_name")
        self.assertEqual(type(col == "foo"), type(filter))
        self.assertEqual("job_name", filter.right.value)

        filter = session._getFuzzyFilterOp(col, "*job*name*")
        self.assertEqual(type(col.like("foo")), type(filter))
        self.assertEqual("$", filter.modifiers["escape"])
        self.assertEqual("%job%name%", filter.right.value)

        filter = session._getFuzzyFilterOp(col, None)
        self.assertEqual(type(col.__eq__(None)), type(filter))
        self.assertEqual(sqlalchemy.sql.elements.Null, type(filter.right))


class TestPostgresqlDatabase(DBBaseTestCase):
    def setUp(self):
        super().setUp()

        f = PostgresqlSchemaFixture(self.id(), self.random_databases,
                                    self.delete_databases)
        self.useFixture(f)
        self.db = f

        config = dict(dburi=f.dburi)
        driver = SQLDriver()
        self.connection = driver.getConnection('database', config)
        self.connection.onLoad(self.zk_client)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        self.connection.onStop()

    def test_migration(self):
        # Test that SQLAlchemy create_all produces the same output as
        # a full migration run.
        pg_dump = os.environ.get("ZUUL_TEST_PG_DUMP", "pg_dump")
        sqlalchemy_out = subprocess.check_output(
            f"{pg_dump} -h {self.db.host} -U {self.db.name} -s {self.db.name}",
            shell=True,
            env={'PGPASSWORD': self.db.passwd}
        )

        with self.connection.engine.begin() as connection:
            tables = [x[0] for x in connection.exec_driver_sql(
                "select tablename from pg_catalog.pg_tables "
                "where schemaname='public'"
            ).all()]

            self.assertTrue(len(tables) > 0)
            for table in tables:
                connection.exec_driver_sql(f"drop table {table} cascade")

        self.connection.force_migrations = True
        self.connection.onLoad(self.zk_client)

        alembic_out = subprocess.check_output(
            f"{pg_dump} -h {self.db.host} -U {self.db.name} -s {self.db.name}",
            shell=True,
            env={'PGPASSWORD': self.db.passwd}
        )
        try:
            self.assertEqual(alembic_out, sqlalchemy_out)
        except Exception:
            differ = difflib.Differ()
            alembic_out = alembic_out.decode('utf8').splitlines()
            sqlalchemy_out = sqlalchemy_out.decode('utf8').splitlines()
            diff = '\n'.join(list(differ.compare(alembic_out, sqlalchemy_out)))
            self.log.debug("Diff:\n%s", diff)
            raise

    def test_migration_f7843ddf1552(self):
        with self.connection.engine.begin() as connection:
            tables = [x[0] for x in connection.exec_driver_sql(
                "select tablename from pg_catalog.pg_tables "
                "where schemaname='public'"
            ).all()]

            self.assertTrue(len(tables) > 0)
            for table in tables:
                connection.exec_driver_sql(f"drop table {table} cascade")

        self.connection.force_migrations = True
        self.connection._migrate('151893067f91')
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("""
            insert into zuul_buildset
            (id, uuid, zuul_ref, project, change, patchset, ref,
             ref_url, oldrev, newrev, branch)
            values
            (1, 'bsuuid1', 'Z1', 'project1',
            1, '1',
            'refs/changes/1',
             'http://project1/1',
            '2d48fe5afe0bc7785294b28e9e96a6c622945b9d',
            '8a938aff20d691d1b9a9f461c6375f0c45acd305',
            'master'),
            (2, 'bsuuid2', 'Z2', 'project1',
            2, 'ee743613ce5b3aee11d12e91e932d7876bc0b40c',
            'refs/changes/2',
             'http://project1/2',
            'bd11c4ff79245ae555418e19840ce4752e48ea38',
            'd1ffc204e4b4955f2a47e7e37618fcf13bb1b9fd',
            'stable'),
            (3, 'bsuuid3', 'Z3', 'project2', NULL, NULL, 'refs/tags/foo',
             'http://project3',
            'a6cf0e07e9e2964a810196f764fc4ac766742568',
            '1a226acbd022968914574fdeb467b78bc5bfcc77',
            NULL)
            """)
            connection.exec_driver_sql("""
            insert into zuul_build
            (id, buildset_id, uuid, job_name, result)
            values
            (1, 1, 'builduuid1', 'job1', 'RESULT1'),
            (2, 1, 'builduuid2', 'job2', 'RESULT2'),
            (3, 2, 'builduuid3', 'job1', 'RESULT3'),
            (4, 2, 'builduuid4', 'job2', 'RESULT4'),
            (5, 3, 'builduuid5', 'job3', 'RESULT5'),
            (6, 3, 'builduuid6', 'job4', 'RESULT6')
            """)

        self.connection._migrate()
        with self.connection.engine.begin() as connection:
            results = [r for r in connection.exec_driver_sql(
                "select b.id, r.ref from zuul_build b join zuul_ref r "
                "on b.ref_id=r.id order by b.id")]
            self.assertEqual(results, [
                (1, 'refs/changes/1'),
                (2, 'refs/changes/1'),
                (3, 'refs/changes/2'),
                (4, 'refs/changes/2'),
                (5, 'refs/tags/foo'),
                (6, 'refs/tags/foo'),
            ])
            results = [r for r in connection.exec_driver_sql(
                "select bs.uuid, r.ref "
                "from zuul_buildset bs, zuul_buildset_ref t, zuul_ref r "
                "where bs.id = t.buildset_id and r.id = t.ref_id "
                "order by bs.uuid")]
            self.assertEqual(results, [
                ('bsuuid1', 'refs/changes/1'),
                ('bsuuid2', 'refs/changes/2'),
                ('bsuuid3', 'refs/tags/foo'),
            ])

    def test_migration_f7843ddf1552_failure(self):
        with self.connection.engine.begin() as connection:
            tables = [x[0] for x in connection.exec_driver_sql(
                "select tablename from pg_catalog.pg_tables "
                "where schemaname='public'"
            ).all()]

            self.assertTrue(len(tables) > 0)
            for table in tables:
                connection.exec_driver_sql(f"drop table {table} cascade")

        self.connection.force_migrations = True
        self.connection._migrate('151893067f91')
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("""
            insert into zuul_buildset
            (id, uuid, zuul_ref, project, change, patchset, ref,
             ref_url, oldrev, newrev, branch)
            values
            (1, 'bsuuid1', 'Z1', 'project1',
            1, '1',
            'refs/changes/1',
             'http://project1/1',
            '2d48fe5afe0bc7785294b28e9e96a6c622945b9d'
            '2d48fe5afe0bc7785294b28e9e96a6c622945b9d',
            '8a938aff20d691d1b9a9f461c6375f0c45acd305',
            'master'),
            (2, 'bsuuid2', 'Z2', 'project1',
            2, 'ee743613ce5b3aee11d12e91e932d7876bc0b40c',
            'refs/changes/2',
             'http://project1/2',
            'bd11c4ff79245ae555418e19840ce4752e48ea38',
            'd1ffc204e4b4955f2a47e7e37618fcf13bb1b9fd',
            'stable'),
            (3, 'bsuuid3', 'Z3', 'project2', NULL, NULL, 'refs/tags/foo',
             'http://project3',
            'a6cf0e07e9e2964a810196f764fc4ac766742568',
            '1a226acbd022968914574fdeb467b78bc5bfcc77',
            NULL)
            """)
            connection.exec_driver_sql("""
            insert into zuul_build
            (id, buildset_id, uuid, job_name, result)
            values
            (1, 1, 'builduuid1', 'job1', 'RESULT1'),
            (2, 1, 'builduuid2', 'job2', 'RESULT2'),
            (3, 2, 'builduuid3', 'job1', 'RESULT3'),
            (4, 2, 'builduuid4', 'job2', 'RESULT4'),
            (5, 3, 'builduuid5', 'job3', 'RESULT5'),
            (6, 3, 'builduuid6', 'job4', 'RESULT6')
            """)

        with testtools.ExpectedException(sqlalchemy.exc.DataError):
            self.connection._migrate()

        with self.connection.engine.begin() as connection:
            tables = [x[0] for x in connection.exec_driver_sql(
                "select tablename from pg_catalog.pg_tables "
                "where schemaname='public'"
            ).all()]
            # Make sure we rolled back the buildset_new table creation
            self.assertNotIn('zuul_buildset_new', tables)
            self.assertIn('zuul_buildset', tables)

    def test_migration_d0a269345a22(self):
        with self.connection.engine.begin() as connection:
            tables = [x[0] for x in connection.exec_driver_sql(
                "select tablename from pg_catalog.pg_tables "
                "where schemaname='public'"
            ).all()]

            self.assertTrue(len(tables) > 0)
            for table in tables:
                connection.exec_driver_sql(f"drop table {table} cascade")

        self.connection.force_migrations = True
        self.connection._migrate('f7843ddf1552')
        with self.connection.engine.begin() as connection:
            connection.exec_driver_sql("""
            insert into zuul_ref
            (id, project, ref, ref_url, change,
            patchset, oldrev, newrev, branch)
            values
            (473951, 'openstack/neutron', 'refs/heads/master',
            'https://git.openstack.org/cgit/openstack/neutron/commit/?id=None',
            0, '', '', '', ''),
            (473958, 'openstack/neutron', 'refs/heads/master',
            'https://git.openstack.org/cgit/openstack/neutron/commit/'
            '?id=fd024ac468456561918e02d32f55eabada102fd3',
            0, '',
            '0017b625ddb64cb3f383e1a4b7f20b7a62153705',
            'fd024ac468456561918e02d32f55eabada102fd3',
            ''),
            (481941, 'openstack/neutron', 'refs/heads/stable/zed',
            'https://opendev.org/openstack/neutron/commit/'
            'd6ee668cc32725cb7d15d2e08fdb50a761f91fe4',
            0, '',
            'fdba20b27a1b97459db1e83f9b235149fe7fd1f7',
            'd6ee668cc32725cb7d15d2e08fdb50a761f91fe4',
            'stable/zed');
            """)
        self.connection._migrate()
        with self.connection.engine.begin() as connection:
            results = [r for r in connection.exec_driver_sql(
                "select id, ref, branch from zuul_ref order by id")]
            self.assertEqual(results, [
                (473951, 'refs/heads/master', 'master'),
                (473958, 'refs/heads/master', 'master'),
                (481941, 'refs/heads/stable/zed', 'stable/zed'),
            ])
