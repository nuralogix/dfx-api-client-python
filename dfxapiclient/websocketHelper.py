import uuid
import websockets


class WebsocketHandler():
    def __init__(self, token, websocket_url):
        self.token = token
        self.ws_url = websocket_url
        self.headers = dict(Authorization="Bearer {}".format(self.token))
        self.ws = None
        self.ws_ID = uuid.uuid4().hex[:10]  # Use same ws_ID for all connections

        # Use this to form a mutual exclusion lock
        self.recv = True

        # Lists for tracking return values
        self.addDataStats = []
        self.subscribeStats = []
        self.chunks = []
        self.unknown = {
        }  # For storing messages not coming from a known websocket sender

    async def connect_ws(self):
        self.ws = await self.handle_connect()

    async def handle_connect(self):
        return await websockets.client.connect(self.ws_url, extra_headers=self.headers)

    async def handle_close(self):
        await self.ws.close()

    async def handle_send(self, content):
        await self.ws.send(content)

    async def handle_recieve(self):
        if self.recv:
            # Mutual exclusion lock; prevents multiple calls of recv() on the same websocket connection
            self.recv = False
            response = await self.ws.recv()
            self.recv = True
        else:
            return

        if response:
            wsID = response[0:10].decode('utf-8')
            # Sort out response messages by type
            if wsID != self.ws_ID:
                self.unknown[wsID] = response

            if len(response) == 13:
                self.subscribeStats.append(response)
            elif len(response) <= 60:
                self.addDataStats.append(response)
            else:
                self.chunks.append(response)
        return
