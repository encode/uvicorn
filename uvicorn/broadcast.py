import asyncio
import asyncio_redis
import collections
import json


class PubSubChannel(object):
    def __init__(self, pub, sub):
        self._pub = pub
        self._sub = sub
        # Keep a mapping from group -> set(channel names)
        self._subscribers = collections.defaultdict(set)

    async def send(self, message):
        group = message['group']
        if 'add' in message:
            if not self._subscribers[group]:
                await self._sub.subscribe([group])
            self._subscribers[group] |= set([message['add']])
        if 'discard' in message:
            self._subscribers[group] -= set([message['discard']])
            if not self._subscribers[group]:
                await self._sub.unsubscribe([group])
        if 'send' in message:
            text = json.dumps(message['send'])
            await self._pub.publish(group, text)


async def listener(sub, subscribers, clients):
    while True:
        reply = await sub.next_published()
        message = json.loads(reply.value)
        for channel_name in subscribers[reply.channel]:
            await clients[channel_name].send(message)


class BroadcastMiddleware(object):
    def __init__(self, asgi, host='localhost', port=6379):
        self.asgi = asgi
        self.host = host
        self.port = port
        self.started = False
        self.clients = {}
        self.pubsub = None

    async def __call__(self, message, channels):
        if self.pubsub is None:
            pub = await asyncio_redis.Connection.create(self.host, self.port)
            sub = await asyncio_redis.Connection.create(self.host, self.port)
            sub = await sub.start_subscribe()
            self.pubsub = PubSubChannel(pub, sub)
            loop = asyncio.get_event_loop()
            loop.create_task(listener(sub, self.pubsub._subscribers, self.clients))

        # Keep track of all connected clients.
        if message['channel'] == 'websocket.connect':
            reply = channels['reply']
            self.clients[reply.name] = reply
        elif message['channel'] == 'websocket.disconnect':
            reply = channels['reply']
            self.clients.pop(reply.name)

        # Inject the groups channel.
        channels['groups'] = self.pubsub

        return await self.asgi(message, channels)
