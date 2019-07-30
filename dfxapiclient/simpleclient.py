import asyncio
import json
import os
import uuid

from .measurements import Measurement
from .organizations import Organization
from .users import User
from .websocketHelper import WebsocketHandler

from .measurements_pb2 import SubscribeResultsRequest


class SimpleClient():
    def __init__(self,
                 license_key,
                 study_id,
                 email,
                 password,
                 server="qa",
                 device_name="DFX desktop",
                 firstname=None,
                 lastname=None,
                 phonenum=None,
                 gender=None,
                 dateofbirth=None,
                 height=None,
                 weight=None,
                 config_file=None,
                 add_method="REST",
                 measurement_mode="DISCRETE",
                 chunk_length=15,
                 video_length=60):

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

        self.__get_urls()
        self.__measurement_mode()

        self.user = User(self.server_url, firstname, lastname, email, password, gender,
                         dateofbirth, height, weight)
        self.organization = Organization(license_key, self.server_url)

        self.addData_done = True  # Can only close websocket after all tasks are done
        self.subscribe_done = True
        self.sub_cycle_complete = True  # Can only create measurement after subscribe is done for previous one
        self.complete = False

        self.subscribe_poll = 0.2  # Time values for signalling and polling
        self.subscribe_signal = 0.5

        self.__setup()  # Register license, create user and login user
        self.__record()  # Record all values and dump into 'default.config'

        self.ws_obj = WebsocketHandler(self.user_token, self.websocket_url)

        self.measurement = Measurement(self.study_id,
                                       self.server_url,
                                       self.ws_obj,
                                       self.num_chunks,
                                       self.max_chunks,
                                       mode=self.measurement_mode,
                                       token=self.user_token)
        self.received_data = self.measurement.received_data

    # Internal: Get server urls given the server name
    def __get_urls(self):
        # North America
        if self.server == "qa":
            self.server_url = "https://qa.api.deepaffex.ai:9443"
            self.websocket_url = "wss://qa.api.deepaffex.ai:9080"

        elif self.server == "dev":
            self.server_url = "https://dev.api.deepaffex.ai:9443"
            self.websocket_url = "wss://dev.api.deepaffex.ai:9080"

        elif self.server == "demo":
            self.server_url = "https://demo.api.deepaffex.ai:9443"
            self.websocket_url = "wss://demo.api.deepaffex.ai:9080"

        elif self.server == "prod":
            self.server_url = "https://api2.api.deepaffex.ai:9443"
            self.websocket_url = "wss://api2.api.deepaffex.ai:9080"

        # China
        elif self.server == "prod-cn":
            self.server_url = "https://api.deepaffex.cn:9443"
            self.websocket_url = "wss://api.deepaffex.cn:9080"

        elif self.server == "demo-cn":
            self.server_url = "https://demo.api.deepaffex.cn:9443"
            self.websocket_url = "wss://demo.api.deepaffex.cn:9080"

        else:
            raise ValueError("Invalid server")

    # Internal: Setup measurement mode
    def __measurement_mode(self):
        if self.measurement_mode == 'DISCRETE':
            max_len = 120
        elif self.measurement_mode == 'BATCH':
            max_len = 1200
        elif self.measurement_mode == 'VIDEO':
            max_len = 1200
        elif self.measurement_mode == 'STREAMING':
            max_len = 1200
        else:
            raise ValueError("Invalid measurement mode given")

        self.num_chunks = int(self.video_length / self.chunk_length)
        self.max_chunks = int(max_len / self.chunk_length)

    # Internal: Record and cache all important parameters
    def __record(self):
        # Create a config file
        if not self.config_file:
            self.config_file = "./default.config"

        if not os.path.isfile(
                self.config_file):  # Create empty config json file if not there
            with open(self.config_file, 'w') as f:
                json.dump({}, f)

        data = {}
        data["license_key"] = self.license_key
        data["server_url"] = self.server_url
        data["websocket_url"] = self.websocket_url
        data["user_email"] = self.user.email
        data["user_password"] = self.user.password
        data["user_id"] = self.user_id
        data["user_token"] = self.user_token
        data["measurement_id"] = self.measurement_id

        with open(self.config_file) as f:
            # Record previous measurement_id and user_id if there is one already
            d = json.load(f)
            if "measurement_id" in d.keys():
                if d["measurement_id"] != '':
                    data["measurement_id"] = d["measurement_id"]
                    self.measurement_id = d["measurement_id"]
                if d["user_id"] != '':
                    data["user_id"] = d["user_id"]
                    self.user_id = d["user_id"]

        with open(self.config_file, mode='w') as f:
            d = json.dumps(data)
            f.write(d)

    # Internal: Set up simpleclient by registering and logging in
    def __setup(self):
        if not self.config_file:
            self.config_file = "./default.config"

        if not os.path.isfile(
                self.config_file):  # Create empty config json file if not there
            with open(self.config_file, 'w') as f:
                json.dump({}, f)

        # Get device token by registering as part of an organization
        out = self.organization.registerLicense(self.device_name)
        if 'Token' not in out:
            print("Registration error. Check your license key or server URL.")
            return

        self.device_token = out['Token']

        # Check if there is an existing user_token. Otherwise it would be redundant to login again
        # Does not create new user or login user if user already logged in
        # (i.e. if there is already a user token in 'default.config')
        with open(self.config_file) as json_file:
            data = json.load(json_file)

            # Try logging in first. Otherwise create the user and then login
            if ('user_token' not in data.keys() or
                    data['user_token'] == '') or (data['server_url'] != self.server_url):
                try:
                    res = self.user.login(self.device_token)
                except:
                    res = self.user.create(self.device_token)
                    if not res:
                        raise Exception("Cannot create user")
                    self.user_id = res

                    res = self.user.login(self.device_token)
                    if not res:
                        raise Exception("User login error")

                self.user_token = self.user.user_token

            else:
                self.user_id = data['user_id']
                self.user_token = data['user_token']
                self.user.user_token = self.user_token

        if self.user_id != '':
            print("\nUser ID:", self.user_id)
            print("Please save the user ID or refer to it using \"client.user_id\"")
        print("\nUser token:", self.user_token)
        print("Please save the user token or refer to it using \"client.user_token\"")
        return

    # Create a new measurement
    def create_new_measurement(self):
        try:
            self.measurement.create()
        except:
            self.clear()
            self.__setup()
            self.__record()
            self.measurement.create()

        self.measurement_id = self.measurement.measurement_id
        print("\nMeasurement ID:", self.measurement_id)
        print(
            "Please save the measurement ID or refer to it using \"client.measurement_id\""
        )

        # Update default.config
        with open(self.config_file) as f:
            d = json.load(f)
            d['measurement_id'] = self.measurement_id
        with open(self.config_file, mode='w') as f:
            data = json.dumps(d)
            f.write(data)
        return self.measurement_id

    # Subscribe to results to this measurement
    async def subscribe_to_results(self, token='', measurement_id=''):
        # If params are not provided, take the last one stored
        with open(self.config_file) as json_file:
            data = json.load(json_file)
            if token == '':
                token = data['user_token']
            if measurement_id == '':
                measurement_id = data['measurement_id']

        if token == '':
            raise ValueError("No user token provided. Please log in.")
        if measurement_id == '':
            raise ValueError("No measurement ID provided. Please create a measurement.")

        self.measurement_id = measurement_id
        self.subscribe_done = False
        self.sub_cycle_complete = False

        # Randomly generated 10-digit hexdecimal request ID
        requestID = uuid.uuid4().hex[:10]  # Or can use requestID = "0000000001"
        actionID = '0510'  # Action ID of the endpoint (see DFX API documentation Section 3.6)

        chunk_no = 0
        while True:
            # Parse request data to proto object
            if not self.sub_cycle_complete:
                request = SubscribeResultsRequest()
                paramval = request.Params
                paramval.ID = self.measurement_id
                request.RequestID = requestID

                data = f'{actionID:4}{requestID:10}'.encode(
                ) + request.SerializeToString()
                done, count = await self.measurement.subscribeResults(
                    data, chunk_num=chunk_no, queue=self.received_data)
            else:
                await asyncio.sleep(self.subscribe_poll)  # For polling
                continue

            self.sub_cycle_complete = True

            if done:
                break
            else:
                chunk_no += count
                await asyncio.sleep(self.subscribe_signal)  # Need to give time to signal

        self.subscribe_done = True
        await self.__handle_exit()

    # Add one chunk of data by passing in the chunk, uses websockets only
    async def add_chunk(self, chunk, token='', measurement_id=''):
        # If params are not provided, take the last one stored
        with open(self.config_file) as json_file:
            data = json.load(json_file)
            if token == '':
                token = data['user_token']
            if measurement_id == '':
                measurement_id = data['measurement_id']

        if token == '':
            raise ValueError("No user token provided. Please log in.")
        if measurement_id == '':
            raise ValueError("No measurement ID provided. Please create a measurement.")

        self.addData_done = False
        self.measurement_id = measurement_id

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
        meta = json.loads(chunk.metadata.decode())

        chunk_num = chunk.chunk_number
        self.num_chunks = chunk.number_chunks

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
        if self.conn_method == "websocket" or self.conn_method == "ws":
            if not self.ws_obj.ws:
                await self.ws_obj.connect_ws()
            response = await self.measurement.add_data_ws(self.measurement_id,
                                                          chunkOrder, action, startTime,
                                                          endTime, duration, payload,
                                                          meta)
            if response:
                status = int(response[10:13].decode('utf-8'))
                body = response.decode('utf-8')
            else:
                self.addData_done = True
        # REST
        else:
            response = await self.measurement.add_data_rest(self.measurement_id,
                                                            chunkOrder, action,
                                                            startTime, endTime, duration,
                                                            payload, meta)
            status = int(response.status_code)
            body = response.json()

        if int(status) != 200:
            print("Response code: ", status)
            print("Response body: ", body)
            if int(status) == 400 or int(status) == 405:
                if chunk_num * duration < 120 and chunk_num != 0:  # Timed out earlier than 120s
                    self.addData_done = True
                    print(
                        "\nAdd data timed out early. Make sure there is only one active measurement under this license."
                    )

                if self.conn_method == "websocket" or self.conn_method == "ws":
                    if 'MEASUREMENT_CLOSED' in body:
                        await self.__handle_ws_timeout(chunkOrder, action, startTime,
                                                       endTime, duration, payload, meta)
                    else:
                        self.addData_done = True
                        print("Cannot add data to this measurement.")
                else:
                    if body['Code'] == 'MEASUREMENT_CLOSED':
                        await self.__handle_ws_timeout(chunkOrder, action, startTime,
                                                       endTime, duration, payload, meta)
                    else:
                        self.addData_done = True
                        print("Cannot add data to this measurement.")
            else:
                self.addData_done = True
                print("Cannot add data to this measurement.")

        # print("\nSleep for the chunk duration")
        await asyncio.sleep(duration)
        await self.__handle_exit()

    # Internal: Handle websocket timeout after 120s for add data
    async def __handle_ws_timeout(self, chunkOrder, action, startTime, endTime, duration,
                                  payload, meta):
        # Need to wait until all previous chunks have been received
        while not self.sub_cycle_complete:  # Poll until subscribe is complete
            await asyncio.sleep(self.subscribe_poll)  # For polling

        # self.retrieve_results()         # Get results from previous measurement
        self.measurement_id = self.create_new_measurement()
        self.sub_cycle_complete = False
        await asyncio.sleep(self.subscribe_signal)

        # Still need to add current chunk to new measurement
        print("\nPrevious measurement timed out. Adding data to new measurement\n")
        if self.conn_method == "websocket" or self.conn_method == "ws":
            response = await self.measurement.add_data_ws(self.measurement_id,
                                                          chunkOrder, action, startTime,
                                                          endTime, duration, payload,
                                                          meta)
            status = int(response[10:13].decode('utf-8'))
            body = response.decode('utf-8')
        else:
            response = await self.measurement.add_data_rest(self.measurement_id,
                                                            chunkOrder, action,
                                                            startTime, endTime, duration,
                                                            payload, meta)
            status = int(response.status_code)
            body = response.json()
        if status != 200:
            print("Response code: ", status)
            print("Response body: ", body)

    # Retrieve results from current measurement
    def retrieve_results(self, token='', measurement_id=''):
        print("\nRetrieving results to this measurement")
        with open(self.config_file) as json_file:
            data = json.load(json_file)
            if token == '':
                token = data['user_token']
            if measurement_id == '':
                measurement_id = data['measurement_id']

        if token == '':
            raise Exception("No user token provided. Please log in.")
        if measurement_id == '':
            raise Exception("No measurement ID provided. Please create a measurement.")

        res = self.measurement.retrieve()
        return res

    # Clear the values in the "default.config" file
    def clear(self):
        with open(self.config_file, mode='w') as f:
            data = {}
            d = json.dumps(data)
            f.write(d)
            # print("\nAll stored values in \'default.config\' have been cleared.")

    # Handle sudden shutdown
    async def shutdown(self):
        self.measurement.end = True
        self.addData_done = True
        await asyncio.sleep(self.subscribe_signal)
        await self.ws_obj.handle_close()
        return

    # Handle exiting
    async def __handle_exit(self):
        if not self.complete:
            if self.addData_done and self.subscribe_done:
                # self.retrieve_results()
                # self.measurement.received_data.task_done()
                if self.conn_method == "websocket" or self.conn_method == "ws":
                    await self.ws_obj.handle_close()
            self.complete = True
