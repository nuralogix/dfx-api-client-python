import uuid

import websockets


class WebsocketHandler():
    """`WebsocketHandler` handles all WebSocket activity within the DFX API.

    It handles all the calls and responses. Also, it enables sending and
    receiving all in one WebSocket connection, through asynchronous programming.
    """
    def __init__(self, token: str, websocket_url: str):
        """Create a `WebsocketHandler` object.

        Arguments:
            token {str} -- user token or device token
            websocket_url {str} -- DFX API Websocket URL
        """
        # Create the header by formatting the token, and generates a 10-digit
        # WebSocket ID.
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
        self.unknown = {}  # For storing messages not coming from a known websocket sender

    async def connect_ws(self):
        """Connect to the Websocket."""
        self.ws = await self.handle_connect()

    async def handle_connect(self):
        """Return a connected Websocket."""
        return await websockets.client.connect(self.ws_url, extra_headers=self.headers)

    async def handle_close(self):
        """Close the Websocket"""
        await self.ws.close()

    async def handle_send(self, content):
        """Send a message on the Websocket

        Arguments:
            content -- Content to send
        """
        await self.ws.send(content)

    async def handle_recieve(self):
        """Handle Websocket receive"""
        # For one WebSocket connection in one thread, there can be at most one
        # call of `ws.recv()` at any given time, otherwise an error will be
        # raised. Therefore, we utilize a mutual exclusion lock using a boolean
        # `self.recv`. In order to make the `ws.recv()` call, we first check
        # if `self.recv == True`. If yes, then we form a lock around
        # `response = await self.ws.recv()` by setting `self.recv = False`
        # first and then `self.recv = True` when it is done. Otherwise,
        # the method returns nothing.
        # *Since `handle_recieve(self)` only makes one `recv()` call at a time,
        # and returns nothing when a `recv()` call cannot be made, it is
        # recommended that you call this method in a polling while loop,
        # for example:*
        # ```python
        # while True:
        #     await self.ws_obj.handle_recieve()
        #     if (...):
        #         ...
        #         break
        # ```

        if self.recv:
            # Mutual exclusion lock; prevents multiple calls of recv() on the same websocket connection
            self.recv = False
            response = await self.ws.recv()
            self.recv = True
        else:
            return

        # If there is a `response`, it first decodes the `wsID` from the
        # response by calling `wsID = response[0:10].decode('utf-8')`.
        # (Reminder that all DFX API websocket responses come in the form
        # `Buffer( [ string:10 ][ string:3 ][ string/buffer ] )`). If the
        # `wsID` is not recognized (i.e. not equal to the `self.ws_ID` for the
        # current connection), we store the wsID and response body into a
        # dictionary called `self.unknown`.

        if response:
            wsID = response[0:10].decode('utf-8')
            # Sort out response messages by type
            if wsID != self.ws_ID:
                self.unknown[wsID] = response

            # Finally, we need to sort the responses by type, to determine
            # whether this is an API response from `add_data` or
            # `subscribe_to_results` (either status or chunk). This can be done
            # by checking the length of each message. It would then add each
            # message into the appropriate list / stack, which would then be
            # retrieved by a parent function.
            if len(response) == 13:
                self.subscribeStats.append(response)
            elif len(response) <= 60:
                self.addDataStats.append(response)
            else:
                self.chunks.append(response)
