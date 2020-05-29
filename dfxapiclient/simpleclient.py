import asyncio
import copy
import json
import os
import uuid

from .measurements import Measurement
from .measurements_pb2 import SubscribeResultsRequest
from .organizations import Organization
from .users import User
from .websocketHelper import WebsocketHandler


class SimpleClient():
    """The DFX API SimpleClient simplifies the process of using the DFX API,
    by providing the following set of core API functionalities:

    Registering a device, creating a user, user login, creating a measurement,
    subscribing to results, adding measurement data and retrieving results

    In subsequent updates, more DFX API endpoints will be added.
    For more information on the DFX API, please see https://dfxapiversion10.docs.apiary.io
    """
    def __init__(self,
                 license_key: str,
                 study_id: str,
                 email: str,
                 password: str,
                 server: str = "prod",
                 device_name: str = "DFX desktop",
                 firstname: str = None,
                 lastname: str = None,
                 phonenum: str = None,
                 gender: str = None,
                 dateofbirth: str = None,
                 height: str = None,
                 weight: str = None,
                 config_file: str = None,
                 add_method: str = "REST",
                 measurement_mode: str = "DISCRETE",
                 chunk_length: float = 15,
                 video_length: float = 60):
        """[summary]

        Arguments:
            license_key {str} -- DFX API License
            study_id {str} -- Study ID
            email {str} -- Email address
            password {str} -- Password

        Keyword Arguments:
            server {str} -- Server to use (default: {"prod"})
            device_name {str} -- Device name (default: {"DFX desktop"})
            firstname {str} -- First name (default: {None})
            lastname {str} -- Last name (default: {None})
            phonenum {str} -- Phone number (default: {None})
            gender {str} -- Gender (default: {None})
            dateofbirth {str} -- Date of birth (default: {None})
            height {str} -- Height (cm) (default: {None})
            weight {str} -- Weight (kg) (default: {None})
            config_file {str} -- Path to save local configuration (default: {None})
            add_method {str} -- Chunk add backend used Websocket or REST (default: {"REST"})
            measurement_mode {str} -- Measurement mode (only DISCRETE supported for now) (default: {"DISCRETE"})
            chunk_length {float} -- Chunk length in seconds (default: {15})
            video_length {float} -- Video length in seconds (default: {60})
        """

        # License key and study ID needs to be provided by the admin
        self.license_key = license_key
        self.study_id = study_id
        self.device_name = device_name
        self.server = server.lower()
        self.conn_method = add_method.lower()
        self.video_length = video_length
        self.chunk_length = chunk_length
        self.measurement_mode = measurement_mode.upper()
        self.config_file = config_file
        self.chunks = None
        self.device_token = ''
        self.device_id = ''
        self.user_id = ''
        self.user_token = ''
        self.measurement_id = ''
        self.received_data = asyncio.Queue(30)  # Queue for storing results

        self.__valid_servers = {}
        self.__measurement_modes = {}
        self.__get_urls()
        self.__measurement_mode()

        self.user = User(self.server_url, firstname, lastname, email, password, gender, dateofbirth, height, weight)
        self.organization = Organization(license_key, self.server_url)

        # Some boolean variables (flags) and floats (time in seconds) for
        # asynchronous signalling purposes.
        self.addData_done = True  # Can only close websocket after all tasks are done
        self.subscribe_done = True
        self.sub_cycle_complete = True  # Can only create measurement after subscribe is done for previous one
        self.complete = False

        self.subscribe_poll = 0.2  # Time values for signalling and polling
        self.subscribe_signal = 0.5

        self.__setup()  # Register license, create user and login user

        self.ws_obj = WebsocketHandler(self.user_token, self.websocket_url)

        self.measurement = Measurement(self.study_id,
                                       self.server_url,
                                       self.ws_obj,
                                       self.num_chunks,
                                       self.max_chunks,
                                       mode=self.measurement_mode,
                                       token=self.user_token)
        self.received_data = self.measurement.received_data

    def __get_urls(self):
        """`Get the REST, websocket, or gRPC urls.

        Raises:
            KeyError: if server key was not in list
        """
        self.__valid_servers = {
            "qa": {
                "server_url": "https://qa.api.deepaffex.ai:9443",
                "websocket_url": "wss://qa.api.deepaffex.ai:9080"
            },
            "dev": {
                "server_url": "https://dev.api.deepaffex.ai:9443",
                "websocket_url": "wss://dev.api.deepaffex.ai:9080"
            },
            "demo": {
                "server_url": "https://demo.api.deepaffex.ai:9443",
                "websocket_url": "wss://demo.api.deepaffex.ai:9080"
            },
            "prod": {
                "server_url": "https://api.deepaffex.ai:9443",
                "websocket_url": "wss://api.deepaffex.ai:9080"
            },
            "prod-cn": {
                "server_url": "https://api.deepaffex.cn:9443",
                "websocket_url": "wss://api.deepaffex.cn:9080"
            },
            "demo-cn": {
                "server_url": "https://demo.api.deepaffex.cn:9443",
                "websocket_url": "wss://demo.api.deepaffex.cn:9080"
            }
        }
        try:
            self.server_url = self.__valid_servers[self.server]["server_url"]
            self.websocket_url = self.__valid_servers[self.server]["websocket_url"]
        except KeyError:
            raise KeyError("Invalid server ID given")

    def __measurement_mode(self):
        """Setup the measurement mode selected by the user.

        Determines the maximum number of chunks for each measurement etc.

        Raises:
            KeyError: if unknown mode was passed
        """
        self.__measurement_modes = {"DISCRETE": 120, "BATCH": 1200, "VIDEO": 1200, "STREAMING": 1200}
        try:
            max_len = self.__measurement_modes[self.measurement_mode]
        except KeyError:
            raise KeyError("Invalid measurement mode given")

        self.num_chunks = int(self.video_length / self.chunk_length)
        self.max_chunks = int(max_len / self.chunk_length)

    def __record(self, data={}):
        """Record and cache all important parameters in a config file

        For this method, if the `data` parameter is not passed in, the new
        values are directly overwritten into the config file.
        If `data` is passed in, it creates a copy. The handling for
        recycling previous values are now implemented in `__setup()` below.

        Keyword Arguments:
            data {dict} -- The data to record(default: {{}})
        """
        # Create a config file
        if not self.config_file:
            self.config_file = "./default.config"

        # Create empty config json file if not there
        if not os.path.isfile(self.config_file):
            with open(self.config_file, 'w') as f:
                d = json.dumps({})
                f.write(d)

        # This structure ensures that for different servers, there can exist
        # multiple licenses (`license_key`), which contains one `device_token`
        # each and multiple users (identified by `user_email`), each with its
        # own `user_token`.

        # Overwrite values with current values
        if not data or data == {}:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                data[self.server] = {}
                if self.license_key != '':
                    data[self.server][self.license_key] = {}
                    if self.device_token != '':
                        data[self.server][self.license_key]["device_token"] = self.device_token
                    if self.user.email != '':
                        data[self.server][self.license_key][self.user.email] = {}
                        if self.user_token != '':
                            data[self.server][self.license_key][self.user.email]["user_token"] = self.user_token
        else:
            data = data

        # Clean up the remaining values (i.e. get rid of it if it's empty)
        copied = copy.deepcopy(data)
        for server in copied.keys():
            if server not in self.__valid_servers.keys():
                data.pop(server, None)

            for key in copied[server].keys():
                data[server].pop('', None)
                data[server].pop(' ', None)
                if copied[server][key] == {}:
                    data[server].pop(key, None)

                for k in copied[server][key].keys():
                    if k != "device_token":
                        data[server][key].pop('', None)
                        data[server][key].pop(' ', None)
                    if copied[server][key][k] == {} or copied[server][key][k] == "":
                        data[server][key].pop(k, None)

        with open(self.config_file, 'w') as f:
            d = json.dumps(data)
            f.write(d)

    def __setup(self):
        """Performs the activities necessary for setting up the client.

        Register license, create user, and authentication / login.
        Recycling and saving the values in configuration file.

        Raises:
            PermissionError: if server error due to permissions.
        """

        #  Create empty config json file if not there.
        if not self.config_file:
            self.config_file = "./default.config"
        if not os.path.isfile(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump({}, f)

        # Recycle and replace values in the config file
        with open(self.config_file, 'r') as json_file:
            data = json.load(json_file)

            # Records the `server`, `license_key`, and `user_email` if they don't exist.
            # Server
            if (self.server not in data.keys() or data[self.server] == {}):
                data[self.server] = {}

            # License key
            if (self.license_key not in data[self.server].keys() or data[self.server][self.license_key] == {}):
                data[self.server][self.license_key] = {}

            # User email
            if self.user.email not in data[self.server][self.license_key].keys():
                data[self.server][self.license_key][self.user.email] = {}

            # Next, if a `device_token` doesn't exist for this server and
            # license, call the `Organization.registerLicense()` endpoint to
            # obtain a device token. On the other hand, if the device token
            # already exists, it takes the existing token to prevent
            # redundantly registering the same license.

            # Device token
            if ("device_token" not in data[self.server][self.license_key].keys()
                    or data[self.server][self.license_key]["device_token"] == ''):
                out = self.organization.registerLicense(self.device_name)
                if 'Token' not in out:
                    self.__record(data=data)  # Save current state
                    raise PermissionError(
                        "Registration error. Make sure your license key is valid for the selected server.")

                self.device_token = out['Token']
                data[self.server][self.license_key]["device_token"] = self.device_token

            elif (self.device_token == '' and data[self.server][self.license_key]["device_token"] != ''):
                self.device_token = data[self.server][self.license_key]["device_token"]

            # Next, if a `user_token` does not exist for the current user on
            # this license and server, it tries to log in (`User.login()`) the
            # user first using the device token. If cannot be logged in, it
            # needs to create a new user (`User.create()`) before logging in.
            # The user information and credentials are already handled in the
            # `User` class, so it only needs to pass in the `device_token`.

            # User token
            if ("user_token" not in data[self.server][self.license_key][self.user.email].keys()
                    or data[self.server][self.license_key][self.user.email]["user_token"] == ''):
                res = self.user.login(self.device_token)

                if res == "INVALID_USER":
                    res = self.user.create(self.device_token)
                    if res == 'INTERNAL_ERROR':
                        self.__record(data=data)
                        raise PermissionError("Cannot create new user. Check your license permissions.")

                    self.user_id = res
                    res = self.user.login(self.device_token)

                elif res == "INVALID_PASSWORD":
                    self.__record(data=data)
                    raise PermissionError("Incorrect login password.")

                self.user_token = self.user.user_token
                if self.user_token != '':
                    data[self.server][self.license_key][self.user.email]["user_token"] = self.user_token
            else:
                self.user_token = data[self.server][self.license_key][self.user.email]["user_token"]
                self.user.user_token = self.user_token

        # Record updated data into the config file.
        self.__record(data=data)

    def create_new_measurement(self) -> str:
        """Create a new measurement by calling to the `create` endpoint under
        `Measurement`.

        Returns:
            str -- Measurement ID
        """
        try:
            self.measurement.create()
        except ValueError:
            # Handling if existing token is invalid
            self.__setup()
            self.measurement.create()

        self.measurement_id = self.measurement.measurement_id
        return self.measurement_id

    #
    async def subscribe_to_results(self, token='', measurement_id=''):
        """Subscribe to results to this measurement by call to the
        `measurement.subscribeResults` endpoint, which requests and establishes
        a websocket connection to receive payloads from a measurement.

        It first checks for the key parameters by reading from the `.config`
        file. This is done in every subsequent method that involve token,
        measurement_id, or folder.

        Keyword Arguments:
            token {str} -- User or device token(default: {''})
            measurement_id {str} -- Measurement ID (default: {''})

        Raises:
            ValueError: If token was not passed or in config file
        """
        # If params are not provided, take the last one stored
        with open(self.config_file) as json_file:
            data = json.load(json_file)
            if token == '':
                token = data[self.server][self.license_key][self.user.email]["user_token"]

        if token == '':
            raise ValueError("No user token provided. Please log in.")
        if not measurement_id or measurement_id == '':
            measurement_id = self.measurement_id

        # Updates some variables and creates the headers. Also generate a 10-digit
        # request ID and sets the action ID, which are needed to make a websocket request.
        self.subscribe_done = False
        self.sub_cycle_complete = False

        # Randomly generated 10-digit hexdecimal request ID
        requestID = uuid.uuid4().hex[:10]  # Or can use requestID = "0000000001"
        actionID = '0510'  # Action ID of the endpoint (see DFX API documentation Section 3.6)

        # Now to make the actual request, we prepare the proto
        # ( `SubscribeResultsRequest` ) and create the `data` buffer in the format
        # `Buffer([ string:4 ][ string:10 ][ string/buffer ])`. It makes a call
        # to the `measurement.subscribeResults` endpoint to subscribe to one
        # measurement.

        # However, for cases where multiple consecutive measurements are needed
        # (since each measurement is limited to 120 seconds long (for discrete
        # measurement mode), any longer measurement must be represented as
        # multiple measurements), a while loop is needed to subscribe to
        # consecutive measurements until all data has been received.

        chunk_no = 0
        while True:
            # Parse request data to proto object
            if not self.sub_cycle_complete:
                request = SubscribeResultsRequest()
                paramval = request.Params
                paramval.ID = measurement_id  # Updates measurement ID
                request.RequestID = requestID

                data = f'{actionID:4}{requestID:10}'.encode() + request.SerializeToString()
                done, count = await self.measurement.subscribeResults(data,
                                                                      chunk_num=chunk_no,
                                                                      result_queue=self.received_data)
            else:
                await asyncio.sleep(self.subscribe_poll)  # For polling
                if self.measurement_id != measurement_id:
                    measurement_id = self.measurement_id
                continue

            self.sub_cycle_complete = True  # Signal that this cycle is complete

            if done:  # If all results have been received, stop the process / cycles
                break
            else:
                chunk_no += count
                await asyncio.sleep(self.subscribe_signal)  # Need to give time to signal

        self.subscribe_done = True  # Signal that the entire process is done
        await self.__handle_exit()

    async def add_chunk(self, chunk, token: str = '', measurement_id: str = ''):
        """Add one chunk of data to a measurement (websockets only)

        Arguments:
            chunk {libdfx.Payload} -- DFX SDK Payload

        Keyword Arguments:
            token {str} -- User or device token(default: {''})
            measurement_id {str} -- Measurement ID (default: {''})

        Raises:
            ValueError: If token was not passed or in config file
        """
        # If params are not provided, take the last one stored
        with open(self.config_file) as json_file:
            data = json.load(json_file)
            if token == '':
                token = data[self.server][self.license_key][self.user.email]["user_token"]

        if token == '':
            raise ValueError("No user token provided. Please log in.")
        if not measurement_id or measurement_id == '':
            measurement_id = self.measurement_id

        self.addData_done = False

        properties = {
            "valid": chunk.valid,
            "start_frame": chunk.start_frame,
            "end_frame": chunk.end_frame,
            "chunk_number": chunk.chunk_number,
            "number_chunks": chunk.number_chunks,
            "first_chunk_start_time_s": chunk.first_chunk_start_time_s,
            "start_time_s": chunk.start_time_s,
            "end_time_s": chunk.end_time_s,
            "duration_s": chunk.duration_s,
        }
        payload = chunk.payload_data
        meta = chunk.metadata

        chunk_num = chunk.chunk_number
        self.num_chunks = chunk.number_chunks

        # Determine action from chunk order
        if chunk_num == 0 and self.num_chunks > 1:
            action = 'FIRST::PROCESS'
        elif chunk_num == self.num_chunks - 1:
            action = 'LAST::PROCESS'
            self.addData_done = True
        else:
            action = 'CHUNK::PROCESS'

        chunkOrder = properties['chunk_number']
        startTime = properties['start_time_s']
        endTime = properties['end_time_s']
        duration = properties['duration_s']

        # Websockets
        status = 0
        body = {}
        if self.conn_method == "websocket" or self.conn_method == "ws":
            if not self.ws_obj.ws:
                await self.ws_obj.connect_ws()
            response = await self.measurement.add_data_ws(measurement_id, chunkOrder, action, startTime, endTime,
                                                          duration, payload, meta)
            if response:
                status = int(response[10:13].decode('utf-8'))
                body = response.decode('utf-8')
            else:
                self.addData_done = True
        # REST
        else:
            response = await self.measurement.add_data_rest(measurement_id, chunkOrder, action, startTime, endTime,
                                                            duration, payload, meta)
            status = int(response.status_code)
            body = response.json()

        # Handle several types of errors.
        # Since `addData` times out after 120s for each measurement, when that
        # happens, we make a call to an internal method `__handle_ws_timeout`.
        # If timeout occurs earlier than 120s, or if there is another type of
        # error, the `addData` process would stop by setting
        # `self.addData_done = True`.
        if int(status) != 200:
            if int(status) == 400 or int(status) == 405:
                if chunk_num * duration < 120 and chunk_num != 0:  # Timed out earlier than 120s
                    self.addData_done = True

                if self.conn_method == "websocket" or self.conn_method == "ws":
                    if 'MEASUREMENT_CLOSED' in body:
                        await self.__handle_ws_timeout(chunkOrder, action, startTime, endTime, duration, payload, meta)
                    else:
                        self.addData_done = True
                else:
                    if body['Code'] == 'MEASUREMENT_CLOSED':
                        await self.__handle_ws_timeout(chunkOrder, action, startTime, endTime, duration, payload, meta)
                    else:
                        self.addData_done = True
            else:
                self.addData_done = True

        # Sleep for the chunk duration as the data gets sent.
        # (This ensures we don't hit the rate limit)
        await asyncio.sleep(duration)

        # Close the websocket connection if all websocket processes are complete.
        await self.__handle_exit()

    async def __handle_ws_timeout(self, chunkOrder: str, action: str, startTime: str, endTime: str, duration: str,
                                  payload: bytes, meta: str):
        """Handle websocket timeout after 120s for add data while there are more
        payload chunks to be added.

        This is a design of the DFX API to prevent having too much data in
        one measurement. In this case, a new measurement would need to be
        created, and both `addData` and `subscribe_to_results` must be
        switched onto the new measurement.

        Arguments:
            chunkOrder {str} -- Chunk Order (from DFX SDK)
            action {str} -- Measurement Action flag
            startTime {str} -- Chunk Start Time (from DFX SDK)
            endTime {str} -- Chunk End Time (from DFX SDK)
            duration {str} -- Chunk Duration (from DFX SDK)
            payload {bytes} -- Chunk Payload Data (from DFX SDK)
            meta {bytes} -- Chunk Payload Metadata (from DFX SDK)
        """
        # Need to wait until all previous chunks have been received
        while not self.sub_cycle_complete:  # Poll until subscribe is complete
            await asyncio.sleep(self.subscribe_poll)  # For polling

        # Get results from previous measurement
        _ = self.retrieve_results()

        # Creare a new measurement, and the subscribe signal is changed and
        # signalled to allow subscribe to continue on the new measurement.
        self.measurement_id = self.create_new_measurement()
        self.sub_cycle_complete = False
        await asyncio.sleep(self.subscribe_signal)

        # Still need to add current chunk to new measurement
        # TODO: Is this still valid
        if self.conn_method == "websocket" or self.conn_method == "ws":
            response = await self.measurement.add_data_ws(self.measurement_id, chunkOrder, action, startTime, endTime,
                                                          duration, payload, meta)
            status = int(response[10:13].decode('utf-8'))
            _ = response.decode('utf-8')
        else:
            response = await self.measurement.add_data_rest(self.measurement_id, chunkOrder, action, startTime, endTime,
                                                            duration, payload, meta)
            status = int(response.status_code)
            _ = response.json()
        if status != 200:
            pass

    # Retrieve results from current measurement
    def retrieve_results(self, token: str = '', measurement_id: str = ''):
        """Retrieve results from current measurement.

        Makes a call to the `measurement.retrieve` endpoint to get results to
        a given measurement.

        Keyword Arguments:
            token {str} -- User or device token(default: {''})
            measurement_id {str} -- Measurement ID (default: {''})

        Raises:
            ValueError: If token was not passed or in config file

        Returns:
            [type] -- [description]
        """
        with open(self.config_file) as json_file:
            data = json.load(json_file)
            if token == '':
                token = data[self.server][self.license_key][self.user.email]["user_token"]

        if token == '':
            raise ValueError("No user token provided. Please log in.")

        if not measurement_id or measurement_id == '':
            res = self.measurement.retrieve()
        else:
            res = self.measurement.retrieve(measurement_id=measurement_id)
        return res

    def clear(self):
        """Clear the values in the "default.config" file"""
        with open(self.config_file, mode='w') as f:
            data = {}
            d = json.dumps(data)
            f.write(d)

    async def shutdown(self):
        """Gracefully shutdown SimpleClient"""

        # Toggles two flags and signals them so the processes can finish.
        # Then it closes the websocket.
        self.measurement.end = True
        self.addData_done = True
        await asyncio.sleep(self.subscribe_signal)
        await self.ws_obj.handle_close()

    # Handle exiting
    async def __handle_exit(self):
        if not self.complete:
            if self.addData_done and self.subscribe_done:
                if self.conn_method == "websocket" or self.conn_method == "ws":
                    await self.ws_obj.handle_close()
            self.complete = True
