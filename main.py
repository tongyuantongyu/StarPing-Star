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
import time
import ipaddress

import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.template
from tornado.log import enable_pretty_logging
import database

enable_pretty_logging()


def limit_request(duration=1):
    def _(async_func):
        v4map = dict()
        v6map = dict()

        @functools.wraps(async_func)
        async def _(self: tornado.web.RequestHandler, *args, **kwargs):
            nonlocal v4map
            nonlocal v6map
            addr = ipaddress.ip_address(self.request.remote_ip)
            now = time.time()
            if isinstance(addr, ipaddress.IPv4Address):
                v4map = {i: j for i, j in v4map.items() if j > now}
                if addr not in v4map:
                    v4map[addr] = time.time() + duration
                    return await async_func(self, *args, **kwargs)
                else:
                    self.set_status(429)
                    await self.finish()
            elif isinstance(addr, ipaddress.IPv6Address):
                v6map = {i: j for i, j in v6map.items() if j > now}
                net = ipaddress.ip_interface(self.request.remote_ip + '/64').network
                if net not in v6map:
                    v6map[net] = time.time() + duration
                    return await async_func(self, *args, **kwargs)
                else:
                    self.set_status(429)
                    await self.finish()

        return _

    return _


class DetailRecordHandler(tornado.web.RequestHandler):
    @limit_request(3)
    async def get(self):
        if 'node' in self.request.arguments and 'target' in self.request.arguments:
            try:
                if 'update' in self.request.arguments and self.request.arguments['update'] == [b'true']:
                    if 'stamp' in self.request.arguments:
                        result, err = await self.settings['db'].query_ping_from(self.request.arguments['node'],
                                                                                self.request.arguments['target'],
                                                                                self.request.arguments['stamp'])
                    else:
                        result, err = None, "Missing parameters."
                else:
                    result, err = await self.settings['db'].query_ping_hours(
                            self.request.arguments['node'], self.request.arguments['target'], 24)
                if err is not None:
                    self.set_status(400)
                    await self.finish('{"message": "' + err + '"}')
                else:
                    self.write(result)
            except ValueError:
                self.set_status(400)
                await self.finish('{"message": "Bad parameter."}')
        else:
            self.set_status(400)
            await self.finish('{"message": "Missing parameters."}')


class RecordHandler(tornado.web.RequestHandler):
    @limit_request()
    async def get(self):
        if 'target' in self.request.arguments:
            try:
                if 'update' in self.request.arguments and self.request.arguments['update'] == [b'true']:
                    if 'stamp' in self.request.arguments:
                        result, err = await self.settings['db'].query_pingavg_from(self.request.arguments['target'],
                                                                                   self.request.arguments['stamp'])
                    else:
                        result, err = None, "Missing parameters."
                else:
                    result, err = await self.settings['db'].query_pingavg_hours(self.request.arguments['target'], 1)
                if err is not None:
                    self.set_status(400)
                    await self.finish('{"message": "' + err + '"}')
                else:
                    self.write(result)
            except ValueError:
                self.set_status(400)
                await self.finish('{"message": "Bad parameter."}')
        else:
            self.set_status(400)
            await self.finish('{"message": "Missing parameters."}')


class LongTermRecordHandler(tornado.web.RequestHandler):
    @limit_request(10)
    async def get(self):
        if 'target' in self.request.arguments and 'span' in self.request.arguments:
            try:
                span = float(self.request.arguments['span'][0])
                if span > 168:
                    self.set_status(400)
                    await self.finish('{"message": "Too long span."}')
                    return
                result, err = await self.settings['db'].query_pingavg_hours(self.request.arguments['target'], span)
                if err is not None:
                    self.set_status(400)
                    await self.finish('{"message": "' + err + '"}')
                else:
                    self.write(result)
            except ValueError:
                self.set_status(400)
                await self.finish('{"message": "Bad parameter."}')
        else:
            self.set_status(400)
            await self.finish('{"message": "Missing parameters."}')


class LongTermDetailRecordHandler(tornado.web.RequestHandler):
    @limit_request(30)
    async def get(self):
        if 'node' in self.request.arguments and 'target' in self.request.arguments and 'span' in self.request.arguments:
            try:
                span = float(self.request.arguments['span'][0])
                if span > 30:
                    self.set_status(400)
                    await self.finish('{"message": "Too long span."}')
                    return
                result, err = await self.settings['db'].query_ping_hours(
                        self.request.arguments['node'], self.request.arguments['target'], 24 * span)
                if err is not None:
                    self.set_status(400)
                    await self.finish('{"message": "' + err + '"}')
                else:
                    self.write(result)
            except ValueError:
                self.set_status(400)
                await self.finish('{"message": "Bad parameter."}')
        else:
            self.set_status(400)
            await self.finish('{"message": "Missing parameters."}')


class RouteHandler(tornado.web.RequestHandler):
    @limit_request()
    async def get(self):
        if 'target' in self.request.arguments and 'node' in self.request.arguments and 'time' in self.request.arguments:
            try:
                result, err = await self.settings['db'].query_mtr_from(self.request.arguments['node'],
                                                                       self.request.arguments['target'],
                                                                       self.request.arguments['time'])
                if err is not None:
                    self.set_status(400)
                    await self.finish('{"message": "' + err + '"}')
                else:
                    if result is None:
                        self.write('{"time": null}')
                    else:
                        self.write(result)
            except ValueError:
                self.set_status(400)
                await self.finish('{"message": "Bad parameter."}')
        else:
            self.set_status(400)
            await self.finish('{"message": "Missing parameters."}')


# WebPages

class MainPageHandler(tornado.web.RequestHandler):
    async def get(self):
        await self.finish(self.settings['template'].load('main.html').generate(
                groups=self.settings['db'].groups,
                group_names=self.settings['db'].group_names
        ))


class GroupPageHandler(tornado.web.RequestHandler):
    async def get(self, group_name):
        if group_name not in self.settings['db'].group_names:
            self.set_status(404)
            await self.finish()
            return
        await self.finish(self.settings['template'].load('group.html').generate(
                groups=self.settings['db'].groups,
                group_name=group_name,
                group_names=self.settings['db'].group_names,
                group_sname=self.settings['db'].group_names[group_name],
                groupv2list=self.settings['db'].group_info[group_name],
                ping_targets=self.settings['db'].ping_targets
        ))


class TargetPageHandler(tornado.web.RequestHandler):
    async def get(self, group_name, target_name):
        if group_name not in self.settings['db'].group_names:
            self.set_status(404)
            await self.finish()
            return
        if target_name not in self.settings['db'].ping_targets:
            self.set_status(404)
            await self.finish()
            return
        nodes = self.settings['db'].ping_targets[target_name][1]
        if 'planet' in nodes:
            nodelist = self.settings['db'].nodes.keys()
        else:
            nodelist = nodes
        await self.finish(self.settings['template'].load('target.html').generate(
                groups=self.settings['db'].groups,
                group_name=group_name,
                target_name=target_name,
                group_names=self.settings['db'].group_names,
                group_sname=self.settings['db'].group_names[group_name],
                target_sname=self.settings['db'].ping_targets[target_name][0],
                nodelist=nodelist,
                nodes=self.settings['db'].nodes
        ))


class RoutePageHandler(tornado.web.RequestHandler):
    async def get(self, group_name, target_name, node_name):
        if group_name not in self.settings['db'].group_names:
            self.set_status(404)
            await self.finish()
            return
        if target_name not in self.settings['db'].ping_targets:
            self.set_status(404)
            await self.finish()
            return
        if node_name not in self.settings['db'].nodes:
            self.set_status(404)
            await self.finish()
            return
        await self.finish(self.settings['template'].load('route.html').generate(
                groups=self.settings['db'].groups,
                group_name=group_name,
                target_name=target_name,
                node_name=node_name,
                group_names=self.settings['db'].group_names,
                group_sname=self.settings['db'].group_names[group_name],
                target_sname=self.settings['db'].ping_targets[target_name][0],
                node_sname=self.settings['db'].nodes[node_name][2],
        ))


class AboutPageHandler(tornado.web.RequestHandler):
    async def get(self):
        await self.finish(self.settings['template'].load('about.html').generate(
                groups=self.settings['db'].groups,
                group_names=self.settings['db'].group_names
        ))


application = tornado.web.Application([
    (r'/api/detailRecord/longterm', LongTermDetailRecordHandler),
    (r'/api/detailRecord', DetailRecordHandler),
    (r'/api/record/longterm', LongTermRecordHandler),
    (r'/api/record', RecordHandler),
    (r'/api/route', RouteHandler),
    (r'/files/(.*)', tornado.web.StaticFileHandler, {"path": "./static/files"}),
    (r'/', MainPageHandler),
    (r'/about', AboutPageHandler),
    (r'/group/(.*)', GroupPageHandler),
    (r'/target/(.*)/(.*)', TargetPageHandler),
    (r'/route/(.*)/(.*)/(.*)', RoutePageHandler)
], debug=True, autoreload=True, compiled_template_cache=False, static_hash_cache=False)

if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    event_loop = asyncio.get_event_loop()
    application.settings['db'] = event_loop.run_until_complete(database.get_db())
    application.settings['template'] = tornado.template.Loader("./static")
    server = tornado.httpserver.HTTPServer(application, xheaders=True)
    server.listen(4081)
    tornado.ioloop.IOLoop.current().start()
