import asyncio
import base64
import json
import uuid

import requests
from dfxapiclient.websocketHelper import WebsocketHandler

from .measurements_pb2 import DataRequest


class Measurement:
    """`Measurement` is used for managing DFX measurement activity.

    This class handles creating a measurement, adding data, subscribing to
    results and retrieving results.

    https://dfxapiversion10.docs.apiary.io/#reference/0/measurements

    *Currently incomplete and more endpoints will be added in subsequent updates.*
    """
    def __init__(self,
                 study_id: str,
                 rest_url: str,
                 ws_obj: WebsocketHandler,
                 num_chunks: int,
                 max_chunks: int,
                 mode: str = 'DISCRETE',
                 token: str = '',
                 usrprofileID: str = ''):
        """Create a `Measurement` object

        Arguments:
            study_id {str} -- Study ID
            rest_url {str} -- REST URL
            ws_obj {WebsocketHandler} -- Websocket handler
            num_chunks {int} -- Number of chunks in measurment
            max_chunks {int} -- Maximum number of chunks

        Keyword Arguments:
            mode {str} -- Measurement mode (default: {'DISCRETE'})
            token {str} -- User or device token (default: {''})
            usrprofileID {str} -- Alternate user profile (default: {''})
        """
        self.study_id = study_id
        self.profile_id = usrprofileID
        self.measurement_id = ''
        self.token = token
        self.url = rest_url
        self.ws_obj = ws_obj
        self.max_chunks = max_chunks
        self.chunks_rem = num_chunks
        self.recv_timeout = 5
        self.received_data = asyncio.Queue(30)
        self.mode = mode
        self.end = False

        auth = 'Bearer ' + token
        self.header = {'Content-Type': 'application/json', 'Authorization': auth}

    # 500
    def retrieve(self, measurement_id: str = None) -> str:
        """Retrieve the results of a measurement using a GET
        https://dfxapiversion10.docs.apiary.io/#reference/0/measurements/retrieve

        Keyword Arguments:
            measurement_id {str} -- Measurement ID (default: {None})

        Raises:
            ValueError: If invalid `measurement_id`

        Returns:
            str -- JSON encoded response
        """
        # [ 500, "1.0", "GET", "retrieve", "/measurements/:ID" ]
        if not measurement_id:
            measurement_id = self.measurement_id
        if not measurement_id or measurement_id == '':
            raise ValueError("No measurement ID given")
        uri = self.url + '/measurements/' + self.measurement_id
        r = requests.get(uri, headers=self.header)
        return r.json()

    # 504
    def create(self) -> str:
        """Creates a new measurement using a POST
        https://dfxapiversion10.docs.apiary.io/#reference/0/measurements/create

        Raises:
            ValueError: If create fails

        Returns:
            str -- Measurement ID for the created measurement
        """
        # [ 504, "1.0", "POST", "create", "/measurements" ]
        values = {"StudyID": self.study_id, "Resolution": 100, "UserProfileID": self.profile_id, "Mode": self.mode}
        values = json.dumps(values)

        uri = self.url + '/measurements'
        r = requests.post(uri, data=values, headers=self.header)
        res = r.json()

        if 'ID' not in res:
            raise ValueError("Could not create measurement")

        self.measurement_id = res['ID']
        return self.measurement_id

    # 506
    # REST
    async def add_data_rest(self, measurement_id: str, chunkOrder: str, action: str, startTime: str, endTime: str,
                            duration: str, payload: bytes, meta: str):
        """Add one payload chunk to a measurement using POST
        https://dfxapiversion10.docs.apiary.io/#reference/0/measurements/add-data

        Arguments:
            measurement_id {str} -- Measurement ID
            chunkOrder {str} -- Chunk Order (from DFX SDK)
            action {str} -- Measurement Action flag
            startTime {str} -- Chunk Start Time (from DFX SDK)
            endTime {str} -- Chunk End Time (from DFX SDK)
            duration {str} -- Chunk Duration (from DFX SDK)
            payload {bytes} -- Chunk Payload Data (from DFX SDK)
            meta {bytes} -- Chunk Payload Metadata (from DFX SDK)

        Returns:
            requests.Response -- response of the POST
        """
        # [ 506, "1.0", "POST", "data", "/measurements/:ID/data" ]
        uri = self.url + "/measurements/" + measurement_id + "/data"

        data = {
            "ChunkOrder": chunkOrder,
            "Action": action,
            "StartTime": startTime,
            "EndTime": endTime,
            "Duration": duration,
            "Meta": str(meta),
            "Payload": base64.b64encode(payload).decode('utf-8')
        }

        result = requests.post(uri, data=json.dumps(data), headers=self.header)
        return result

    # Websocket
    async def add_data_ws(self, measurement_id: str, chunkOrder: str, action: str, startTime: str, endTime: str,
                          duration: str, payload: bytes, meta: str):
        """Add one payload chunk to a measurement using Websockets.
        https://dfxapiversion10.docs.apiary.io/#reference/0/measurements/add-data

        The data is converted to a `DataRequest` protobuf, then combined
        with a 10-digit `requestID` and 4-digit `actionID` to get the
        format `Buffer( [ string:4 ][ string:10 ][ string/buffer ] )`,
        before it is sent.

        Arguments:
            measurement_id {str} -- Measurement ID
            chunkOrder {str} -- Chunk Order (from DFX SDK)
            action {str} -- Measurement Action flag
            startTime {str} -- Chunk Start Time (from DFX SDK)
            endTime {str} -- Chunk End Time (from DFX SDK)
            duration {str} -- Chunk Duration (from DFX SDK)
            payload {bytes} -- Chunk Payload Data (from DFX SDK)
            meta {bytes} -- Chunk Payload Metadata (from DFX SDK)

        Returns:
            Union[str, bytes] -- Websocket response
        """
        data = DataRequest()
        paramval = data.Params
        paramval.ID = measurement_id

        data.ChunkOrder = chunkOrder
        data.Action = action
        data.StartTime = startTime
        data.EndTime = endTime
        data.Duration = duration
        data.Meta = meta
        data.Payload = bytes(payload)  # Payload has to be encoded to base 64

        # Randomly generated 10-digit hexdecimal request ID
        requestID = uuid.uuid4().hex[:10]  # Or can use requestID = "0000000001"

        actionID = '0506'  # Action ID of the endpoint (see DFX API documentation Section 3.6)

        # Must be in the following format
        data = f'{actionID:4}{requestID:10}'.encode() + data.SerializeToString()

        response = ""
        await self.ws_obj.handle_send(data)

        # To receive a response, polling must be done (using a `while` loop),
        # since otherwise there could be a deadlock if nothing is being
        # received (the program will get stuck / blocked at receive).
        # By using `await asyncio.wait_for`, it also allows context switching
        # in the asyncio event loop while polling for the result.

        while True:
            if not self.end:
                try:
                    await asyncio.wait_for(self.ws_obj.handle_recieve(), timeout=self.recv_timeout)
                except Exception:
                    if self.end:
                        break
                    else:
                        continue
                if self.ws_obj.addDataStats:
                    response = self.ws_obj.addDataStats[0]
                    self.ws_obj.addDataStats = self.ws_obj.addDataStats[1:]
                    break
            else:
                return

        return response

    # 510
    async def subscribeResults(self, data: bytes, chunk_num: int, result_queue: asyncio.Queue):
        """Creates a websocket connection to receive the results for chunk sent
        for measurement and stop when all the chunks are received.
        https://dfxapiversion10.docs.apiary.io/#reference/0/measurements/subscribe-to-results

        Arguments:
            data {bytes} -- Input data

        Keyword Arguments:
            chunk_num {int} -- Chunk number
            result_queue {asyncio.Queue} -- Queue where results will be store

        Raises:
            ValueError: [description]
            ValueError: [description]
            ValueError: [description]

        Returns:
            [type] -- [description]
        """
        # [ 510, "1.0", "CONNECT", "subscribeResults", "/measurements/:ID/results/" ]

        # All the websocket interaction is done with a `WebsocketHandler` object
        # `self.ws_obj`.
        # It first sends the `data` buffer to the websocket to make the initial
        # subscribe request. Then, to determine when to stop subscribing, the
        # number of chunks need to be calculated. This takes into consideration
        # that a maximum of 120s of data can be sent to one measurement at a
        # time. The limit can therefore be calculated given the chunk duration,
        # and is stored in `self.max_chunks`. `self.chunks_rem` keeps track of
        # the number of remaining chunks
        if not self.ws_obj.ws:
            await self.ws_obj.connect_ws()
        await self.ws_obj.handle_send(data)

        done = False
        counter = chunk_num
        if self.chunks_rem < 0:
            raise ValueError("Invalid number of chunks")
        if self.chunks_rem > self.max_chunks:
            num_limit = chunk_num + self.max_chunks
            self.chunks_rem -= self.max_chunks
        else:
            num_limit = chunk_num + self.chunks_rem
            self.chunks_rem = 0

        # In the main loop, in each iteration a response is received from the
        # websocket. The response can either be a confirmation status, or can
        # be a payload chunk. This is already sorted out by
        # `ws_obj.handle_recieve()` into two stacks, `ws_obj.subscribeStats` for
        # statuses, and `ws_obj.chunks` for payload chunks.

        while counter < num_limit:
            if not self.end:  # For handling early exit
                try:
                    await self.ws_obj.handle_recieve()
                except Exception:
                    if self.end:
                        break
                    else:
                        continue

                if self.ws_obj.subscribeStats:  # If response is a confirmation status
                    response = self.ws_obj.subscribeStats[0]
                    self.ws_obj.subscribeStats = self.ws_obj.subscribeStats[1:]
                    statusCode = response[10:13].decode('utf-8')
                    if statusCode != '200':
                        raise ValueError(f"Status Code{statusCode}: Subscribe failed. (Check measurement ID)")
                elif self.ws_obj.chunks:  # If response is a payload chunk
                    counter += 1
                    response = self.ws_obj.chunks[0]
                    self.ws_obj.chunks = self.ws_obj.chunks[1:]

                    # Store results in queue
                    if result_queue:
                        await result_queue.put(response[13:])

                    if len(response[13:]) < 1000:
                        raise ValueError(f"Status Code{response[13:]}: Subscribe failed. (Check measurement ID)")
            else:
                done = True
                return done, counter

        # After this iteration is done, a boolean status `done` and the
        # `counter` are returned. This enables another call of
        # `subscribe_to_results` if multiple measurements were created and not
        # all data has been received yet.

        if self.chunks_rem > 0:
            done = False
        else:
            done = True

        return done, counter
