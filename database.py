# StarPing Star
# Copyright (C) 2020  Yuan Tong
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import functools
import asyncpg
import json
import time
import config
from collections import ChainMap
import credential


def unsafe(name):
    return bool(set(name) - config.safe_name)


def array(nodes):
    return '{' + ', '.join(nodes) + '}'


def round_ping_time(t):
    return t / 1000000000 // config.ping_config["frequency"] * config.ping_config["frequency"]


def round_mtr_time(t):
    return t / 1000000000 // config.mtr_config["frequency"] * config.mtr_config["frequency"]


def with_db(async_func):
    @functools.wraps(async_func)
    async def _(self, *args, **kwargs):
        async with self.pool.acquire() as db:
            return await async_func(db, *args, **kwargs)

    return _


def with_self_db(async_func):
    @functools.wraps(async_func)
    async def _(self, *args, **kwargs):
        async with self.pool.acquire() as db:
            return await async_func(self, db, *args, **kwargs)

    return _


def unpack(async_func):
    @functools.wraps(async_func)
    async def _(self, *args, **kwargs):
        arg = []
        for i in args:
            try:
                arg.append(i[0].decode())
            except (TypeError, AttributeError):
                arg.append(i)
        kwarg = dict()
        for i, v in kwargs.items():
            try:
                kwarg[i] = v[0].decode()
            except (TypeError, AttributeError):
                kwarg[i] = v
        return await async_func(self, *arg, **kwarg)

    return _


class Database:
    def __init__(self, *args, **kwargs):
        self._pool = asyncpg.create_pool(*args, **kwargs)

    async def connect(self):
        self.pool = await self._pool
        await self.refresh_cache()

    @with_self_db
    async def refresh_cache(self, db):
        await self._get_node_list(db)
        await self._get_ping_targets_list(db)
        await self._get_mtr_targets_list(db)
        await self._get_group_name(db)
        await self._get_group_info(db)

    async def _get_node_list(self, db: asyncpg.Connection):
        self.nodes = {i['name']: (i['secret'], i['type'], i['shown_name']) for i in
                      await db.fetch('select name, secret, type, shown_name from StarPing_Nodes;')}

    async def _get_ping_targets_list(self, db: asyncpg.Connection):
        self.ping_targets = {i['name']: (i['shown_name'], i['nodes']) for i in
                             await db.fetch('select name, shown_name, nodes from StarPing_PingTargets;')}

    async def _get_mtr_targets_list(self, db: asyncpg.Connection):
        self.mtr_targets = {i['name']: (i['shown_name'], i['nodes']) for i in
                            await db.fetch('select name, shown_name, nodes from StarPing_MTRTargets;')}

    async def _get_group_name(self, db: asyncpg.Connection):
        self.group_names = {i['name']: i['shown_name'] for i in
                            await db.fetch('select name, shown_name from StarPing_L2TargetGroup;')}

    async def _get_group_info(self, db: asyncpg.Connection):
        group_info = json.loads(await db.fetchval(
                "SELECT json_agg(s.r) g FROM (SELECT name, json_build_object(name, ("
                "SELECT json_agg(t.name) FROM (SELECT name FROM StarPing_PingTargets "
                "WHERE group_name = StarPing_L2TargetGroup.name) t"
                ")) AS r FROM StarPing_L2TargetGroup) s where s.r->>s.name != 'null';"))
        self.group_info = ChainMap(*group_info)
        v2groups = set(self.group_info.keys())
        groups = json.loads(await db.fetchval(
                "SELECT json_agg(r.t) FROM (SELECT json_build_object(p.name, p.q) t FROM ("
                "SELECT name, (SELECT json_build_object("
                "'shown_name', StarPing_L1TargetGroup.shown_name,"
                "'child', json_object(array_agg(s.name), array_agg(s.shown_name))"
                ") g FROM (SELECT name, shown_name FROM StarPing_L2TargetGroup "
                "WHERE parent = StarPing_L1TargetGroup.name"
                ") s) q FROM StarPing_L1TargetGroup) p where p.q->>'child' != 'null') r;"))
        groups = {j['shown_name']: v2groups.intersection(j['child']) for i, j in ChainMap(*groups).items()}
        self.groups = {i: j for i, j in groups.items() if j}

    @with_db
    async def get_secret(db: asyncpg.Connection, name):
        return await db.fetchrow(f"select secret, type from StarPing_Nodes where name = '{name}';")

    @with_db
    async def get_target(db: asyncpg.Connection, name, typ='planet'):
        return list(str(i['ip']) for i in await db.fetch(
                f"select ip from StarPing_PingTargets where '{typ}' = ANY(nodes) or '{name}' = ANY(nodes);")), \
               list(str(i['ip']) for i in await db.fetch(
                       f"select ip from StarPing_MTRTargets where '{typ}' = ANY(nodes) or '{name}' = ANY(nodes);"))

    @with_db
    async def ping_record(db: asyncpg.Connection, planet, p):
        await db.execute("insert into StarPing_PingData "
                         "(node, time, name, timeout, avg, min, max, std_dev, drop, total) VALUES "
                         f"('{planet}', to_timestamp({round_ping_time(p['time'])}), "
                         f"(select name from StarPing_PingTargets where ip = '{p['report']['ip']}'), "
                         f"{p['report']['stat']['timeout']}, {p['report']['stat']['avg']}, "
                         f"{p['report']['stat']['min']}, {p['report']['stat']['max']}, "
                         f"{p['report']['stat']['std_dev']}, {p['report']['stat']['drop']}, "
                         f"{p['report']['stat']['total']});")

    @with_db
    async def mtr_record(db: asyncpg.Connection, planet, p):
        await db.execute("insert into StarPing_MTRData "
                         "(node, time, name, hop_count, data) VALUES "
                         f"('{planet}', to_timestamp({round_mtr_time(p['time'])}), "
                         f"(select name from StarPing_MTRTargets where ip = '{p['report']['ip']}'), "
                         f"{p['report']['hop_count']}, '{json.dumps(p['report']['stat'])}');")

    @with_self_db
    async def add_new_node(self, db: asyncpg.Connection, name, secret, typ, sname=None):
        if typ not in ('planet', 'comet'):
            raise RuntimeError(f'"{typ}" is not a valid type.')
        if unsafe(name) or name in ('planet', 'comet'):
            raise RuntimeError(f'"{name}" can\'t be used as a {typ} name.')
        if sname is None:
            sname = name
        async with db.transaction():
            exist = await db.fetchval(f"select type from StarPing_Nodes where name = '{name}';")
            if exist:
                raise RuntimeError(f'A {exist} named "{name}" already exists.')
            await db.execute(f"INSERT INTO StarPing_Nodes (name, secret, type, shown_name) "
                             f"VALUES ('{name}', '{secret}', '{typ}', '{sname}');")
            await db.execute(
                    f"CREATE TABLE StarPing_PingData_{name} PARTITION OF StarPing_PingData FOR VALUES IN ('{name}');")
            await db.execute(
                    f"CREATE TABLE StarPing_MTRData_{name} PARTITION OF StarPing_MTRData FOR VALUES IN ('{name}');")
        # Refresh node list cache.
        await self._get_node_list(db)

    @with_self_db
    async def remove_exist_node(self, db: asyncpg.Connection, name):
        if unsafe(name):
            raise RuntimeError(f'"{name}" can\'t be a valid name.')
        async with db.transaction():
            exist = await db.fetchval(f"select type from StarPing_Nodes where name = '{name}';")
            if not exist:
                raise RuntimeError(f'A No node named "{name}" exists.')
            # Remove records
            await db.execute(f"DROP TABLE StarPing_PingData_{name};")
            await db.execute(f"DROP TABLE StarPing_MTRData_{name};")
            # Remove entry
            await db.execute(f"DELETE FROM StarPing_Nodes WHERE name = '{name}';")
            # Remove configuration
            await db.execute(f"update StarPing_PingTargets set nodes = drop_array_item(nodes, '{name}');")
            await db.execute(f"update StarPing_MTRTargets set nodes = drop_array_item(nodes, '{name}');")
        # Refresh node list cache.
        await self._get_node_list(db)
        await self._get_ping_targets_list(db)
        await self._get_mtr_targets_list(db)

    @with_self_db
    async def add_ping_target(self, db: asyncpg.Connection, name, ip, group='default', nodes=None, sname=None):
        if name in ('planet', 'comet'):
            raise RuntimeError(f'"{name}" can\'t be used as a target name.')
        if nodes is None:
            nodes = ['planet']
        if sname is None:
            sname = name
        await db.execute("INSERT INTO StarPing_PingTargets (name, ip, nodes, shown_name, group_name) VALUES "
                         f"('{name}', '{ip}', '{array(nodes)}', '{sname}', '{group}');")
        await self._get_ping_targets_list(db)

    @with_self_db
    async def add_mtr_target(self, db: asyncpg.Connection, name, ip, nodes=None, sname=None):
        if name in ('planet', 'comet'):
            raise RuntimeError(f'"{name}" can\'t be used as a target name.')
        if nodes is None:
            nodes = ['planet']
        if sname is None:
            sname = name
        await db.execute("INSERT INTO StarPing_MTRTargets (name, ip, nodes, shown_name) VALUES "
                         f"('{name}', '{ip}', '{array(nodes)}', '{sname}');")
        await self._get_mtr_targets_list(db)

    @with_self_db
    async def add_target(self, db: asyncpg.Connection, name, ip, group='default', nodes=None, sname=None):
        if name in ('planet', 'comet'):
            raise RuntimeError(f'"{name}" can\'t be used as a target name.')
        if nodes is None:
            nodes = ['planet']
        if sname is None:
            sname = name
        await db.execute("INSERT INTO StarPing_PingTargets (name, ip, nodes, shown_name, group_name) VALUES "
                         f"('{name}', '{ip}', '{array(nodes)}', '{sname}', '{group}');")
        await db.execute("INSERT INTO StarPing_MTRTargets (name, ip, nodes, shown_name) VALUES "
                         f"('{name}', '{ip}', '{array(nodes)}', '{sname}');")
        await self._get_ping_targets_list(db)
        await self._get_mtr_targets_list(db)

    @with_self_db
    async def add_l1_group(self, db: asyncpg.Connection, name, sname=None):
        if name in ('planet', 'comet'):
            raise RuntimeError(f'"{name}" can\'t be used as a group name.')
        if sname is None:
            sname = name
        await db.execute(f"INSERT INTO StarPing_L1TargetGroup (name, sname) VALUES ('{name}', '{sname}')")

    @with_self_db
    async def add_l2_group(self, db: asyncpg.Connection, name, sname=None):
        if name in ('planet', 'comet'):
            raise RuntimeError(f'"{name}" can\'t be used as a group name.')
        if sname is None:
            sname = name
        await db.execute(f"INSERT INTO StarPing_L1TargetGroup (name, sname) VALUES ('{name}', '{sname}')")

    # ----------
    # Functions above are considered safe as they are called by either the admin or the nodes.
    # Functions below are serving queries.sql from website users and should be designed carefully
    # to prevent SQL injection vulnerabilities.
    # ----------

    def check_planet(self, planet):
        if unsafe(planet):
            return "Unsafe query."
        if planet not in self.nodes or self.nodes[planet][1] != 'planet':
            return "Non-exist planet."

    def check_comet(self, comet):
        if unsafe(comet):
            return "Unsafe query."
        if comet not in self.nodes or self.nodes[comet][1] != 'comet':
            return "Non-exist comet."

    def check_node(self, node):
        if unsafe(node):
            return "Unsafe query."
        if node not in self.nodes:
            return "Non-exist node."

    def check_pingtarget(self, target):
        if unsafe(target):
            return "Unsafe query."
        if target not in self.ping_targets:
            return "Non-exist target."

    @staticmethod
    def check_time(start, end=None):
        if end is None:
            if start < 0:
                return "Invalid time."
        elif start > end or start < 0 or end < 0:
            return "Bad time range."

    @with_self_db
    async def _query_ping_timespan(self, db: asyncpg.Connection, planet, target, start, end):
        # parameter safety check
        err = self.check_planet(planet)
        if err is not None:
            return None, err
        err = self.check_pingtarget(target)
        if err is not None:
            return None, err
        err = self.check_time(start, end)
        if err is not None:
            return None, err

        return await db.fetchval("SELECT json_build_object("
                                 "'time', json_agg(stamp),"
                                 "'timeout', json_agg(timeout),"
                                 "'avg', json_agg(avg),"
                                 "'min', json_agg(min),"
                                 "'max', json_agg(max),"
                                 "'std_dev', json_agg(std_dev),"
                                 "'drop', json_agg(drop),"
                                 "'total', json_agg(total)"
                                 ") FROM ("
                                 "SELECT extract(epoch from time) stamp, timeout, avg, min, max, std_dev, drop, total "
                                 f"from StarPing_PingData where node = '{planet}' and name = '{target}' and "
                                 f"time > to_timestamp({start}) and time <= to_timestamp({end}) order by stamp"
                                 ") t;"), None

    # @with_self_db
    # async def query_ping_latest(self, db: asyncpg.Connection, planet, target):
    #     # parameter safety check
    #     err = self.check_planet(planet)
    #     if err is not None:
    #         return None, err
    #     err = self.check_pingtarget(target)
    #     if err is not None:
    #         return None, err
    #     return await db.fetchval("SELECT json_agg(t) FROM ("
    #                              "SELECT extract(epoch from time) stamp, timeout, avg, min, max, std_dev, drop, total "
    #                              f"from StarPing_PingData where name = '{target}' and node = '{planet}' "
    #                              f"and time = (select max(time) from StarPing_PingData where name = '{target}' "
    #                              f"and node = '{planet}')) t;"), None

    @unpack
    async def query_ping_hours(self, planet, target, hours):
        if hours <= 0:
            return None, "Bad time."
        now = time.time()
        return await self._query_ping_timespan(planet, target, now - 3600 * hours, now)

    @unpack
    async def query_ping_timespan(self, planet, target, start, end):
        return await self._query_ping_timespan(planet, target, start, end)

    @unpack
    async def query_ping_from(self, planet, target, stamp):
        now = time.time()
        stamp = float(stamp)
        if stamp <= 0 or stamp > now:
            return None, "Bad time."
        return await self._query_ping_timespan(planet, target, stamp, now)

    @with_self_db
    async def _query_pingavg_timespan(self, db: asyncpg.Connection, target, start, end):
        # parameter safety check
        err = self.check_pingtarget(target)
        if err is not None:
            return None, err
        err = self.check_time(start, end)
        if err is not None:
            return None, err
        return await db.fetchval("select json_agg(s) from (select name, shown_name, (select json_agg(t) from ("
                                 "select extract(epoch from time) stamp, timeout, avg from "
                                 f"StarPing_PingData where node = StarPing_Nodes.name and name = '{target}' "
                                 f"and time > to_timestamp({start}) and time <= to_timestamp({end}) order by stamp"
                                 ") t) as data from StarPing_Nodes where type = 'planet') s;"), None

    @unpack
    async def query_pingavg_hours(self, target, hours):
        if hours <= 0:
            return None, "Bad time."
        now = time.time()
        return await self._query_pingavg_timespan(target, now - 3600 * hours, now)

    @unpack
    async def query_pingavg_timespan(self, target, start, end):
        return await self._query_pingavg_timespan(target, start, end)

    @unpack
    async def query_pingavg_from(self, target, stamp):
        now = time.time()
        stamp = float(stamp)
        if stamp <= 0 or stamp > now:
            return None, "Bad time."
        return await self._query_pingavg_timespan(target, stamp, now)

    @with_self_db
    async def _query_mtr_from(self, db: asyncpg.Connection, node, target, stamp):
        # parameter safety check
        err = self.check_node(node)
        if err is not None:
            return None, err
        err = self.check_pingtarget(target)
        if err is not None:
            return None, err
        return await db.fetchval("select json_build_object('time', t.stamp, 'data', t.data) from (SELECT\n"
                                 f"extract(epoch from time) stamp, data from StarPing_MTRData where node = '{node}'\n"
                                 f"and name = '{target}' and time > to_timestamp({stamp}) order by time limit 1) t;"), None

    @unpack
    async def query_mtr_from(self, node, target, stamp):
        now = time.time()
        stamp = float(stamp)
        if stamp <= 0 or stamp > now:
            return None, "Bad time."
        return await self._query_mtr_from(node, target, stamp)


async def get_db():
    database = Database(**credential.database_login)
    await database.connect()
    return database
