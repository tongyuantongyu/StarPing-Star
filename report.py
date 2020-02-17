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

import asyncio
import platform
import functools
import hashlib
import hmac
import json
import warnings
from typing import Iterable

import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.template
from tornado.log import enable_pretty_logging
import asyncpg
import database
import config
import credential

enable_pretty_logging()


def first_true(i: Iterable[str]):
    for j in i:
        if j:
            return j.encode()
    return None


def verify_hmac(data="body"):
    def _(async_func):
        @functools.wraps(async_func)
        async def verify(self: tornado.web.RequestHandler, *args, **kwargs):
            self.set_header("Content-Type", "application/json")
            if 'X-StarPing-Name' not in self.request.headers \
                    or 'X-StarPing-Signature' not in self.request.headers:
                self.set_status(403)
                await self.finish('{"message": "Signature header absent."}')
                return
            name = self.request.headers['X-StarPing-Name']
            # Take care of SQL injection
            if set(name) - config.safe_name:
                self.set_status(400)
                await self.finish('{"message": "Malformed name."}')
                return
            node = await self.settings['db'].get_secret(name)
            if not node:
                self.set_status(403)
                await self.finish('{"message": "Not registered planet."}')
                return
            secret, typ = node['secret'].encode(), node['type']
            verify_data = None
            if data == "body":
                verify_data = self.request.body
            elif data.startswith("header"):
                fields = data[6:].split(",")
                if not fields[0]:
                    verify_data = name.encode()
                else:
                    verify_data = first_true(self.request.headers[i] for i in fields if i in self.request.headers)
            if not verify_data:
                self.set_status(400)
                await self.finish('{"message": "Can\'t verify node."}')
                return
            if not hmac.compare_digest(
                    hmac.HMAC(secret, verify_data, hashlib.sha256).hexdigest(),
                    self.request.headers['X-StarPing-Signature']):
                self.set_status(403)
                await self.finish('{"message": "Bad signature."}')
                return
            return await async_func(self, *args, name=name, typ=typ, **kwargs)

        return verify

    return _


class DatabaseWarning(Warning):
    pass


class ConfigHandler(tornado.web.RequestHandler):
    @verify_hmac('header')
    async def get(self, name, typ):
        ping_targets, mtr_targets = await self.settings['db'].get_target(name)
        if not ping_targets and not mtr_targets:
            self.set_status(500)
            await self.finish('{"message": "No target configured for this planet. Possibly config inconsistent."}')
            warnings.warn(f"No target configured for {typ} '{name}'. Is database inconsistent?", DatabaseWarning)
            return
        ping_config, mtr_config = config.get_config()
        if 'update' in self.request.arguments:
            data = json.dumps({
                "ping_targets": ping_targets,
                "mtr_targets": mtr_targets
            }).encode()
            self.write(data)
        else:
            data = json.dumps({
                "ping_config": ping_config,
                "mtr_config": mtr_config,
                "ping_targets": ping_targets,
                "mtr_targets": mtr_targets
            }).encode()
            self.write(data)


class ReportHandler(tornado.web.RequestHandler):
    @verify_hmac()
    async def post(self, name, typ):
        if 'type' in self.request.arguments:
            try:
                if self.request.arguments['type'] == [b'ping']:
                    if typ == 'planet':
                        p = json.loads(self.request.body)
                        await self.settings['db'].ping_record(name, p)
                    else:
                        print(f'Bad request: {self.request.arguments["type"]}')
                        self.set_status(400)
                        await self.finish('{"message": "Comets shouldn\'t report ping records."}')
                elif self.request.arguments['type'] == [b'mtr']:
                    p = json.loads(self.request.body)
                    await self.settings['db'].mtr_record(name, p)
                else:
                    print(f'Bad request: {self.request.arguments["type"]}')
                    self.set_status(400)
                    await self.finish('{"message": "Unacceptable report type."}')
            except json.JSONDecodeError:
                self.set_status(400)
                await self.finish('{"message": "Bad JSON report."}')
            except asyncpg.PostgresError:
                # Star *TRUST* data sent by Planets and Comets after secret being verified.
                # Never blindly add planets or comets from untrusted source.
                self.set_status(400)
                await self.finish('{"message": "Bad report value."}')
        else:
            self.set_status(400)
            await self.finish('{"message": "No type specified."}')


class ReloadHandler(tornado.web.RequestHandler):
    async def get(self):
        if self.request.remote_ip == '127.0.0.1' or self.request.remote_ip == '::1':
            self.settings['db'].refresh_cache()


application = tornado.web.Application([
    (r'/nodes/api/report', ReportHandler),
    (r'/nodes/api/config', ConfigHandler),
    (rf'/nodes/api/reload/{credential.reload_key}', ReloadHandler)
])


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    event_loop = asyncio.get_event_loop()
    application.settings['db'] = event_loop.run_until_complete(database.get_db())
    server = tornado.httpserver.HTTPServer(application, xheaders=True)
    server.listen(4080)
    tornado.ioloop.IOLoop.current().start()
