# SimpleClient

This is the class definition for the DFX API SimpleClient. It significantly simplifies the process of using the DFX API, by providing the following set of core API functionalities:

* Registering a device
* Creating a user
* User login
* Creating a measurement
* Subscribing to results
* Adding measurement data
* Retrieving results

In subsequent updates, more DFX API functionalities (endpoints) will be provided. For more information on the DFX API, please see the [Apiary documentation](https://dfxapiversion10.docs.apiary.io)

This is a detailed documentation of the SimpleClient. For basic usage of the SimpleClient, refer to `README.md` and `test.py`.

The SimpleClient depends on the following packages:

```python
# Python dependancies
import asyncio
import copy
import json
import os
import uuid

# Other objects from this library
from .measurements import Measurement
from .organizations import Organization
from .users import User
from .websocketHelper import WebsocketHandler

# Complied proto files for websocket requests
from .measurements_pb2 import SubscribeResultsRequest
```

## Constructor

The constructor method takes in all the needed information at once for DFX API activity. All parameters must be in `string` format. It then saves this information in the class and in a `.config` file so the user no longer needs to refer to them again when calling any method.

```python
__init__(self,
         license_key:str,
         study_id:str,
         email:str,
         password:str,
         server:str="qa",
         device_name:str="DFX desktop",
         firstname:str=None,
         lastname:str=None,
         phonenum:str=None,
         gender:str=None,
         dateofbirth:str=None,
         height:str=None,
         weight:str=None,
         config_file:str=None,
         add_method:str="REST",
         measurement_mode:str="DISCRETE",
         chunk_length:int=15,
         video_length:int=60
        )
```

The following variables are recorded and can be referenced by calling `client.variable_name`.

```python
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
self.received_data = asyncio.Queue(30)      # Queue for storing results
```

Some boolean variables (flags) and floats (time in seconds) are defined for asynchronous signalling purposes.

```python
self.addData_done = True
self.subscribe_done = True
self.sub_cycle_complete = True
self.complete = False

self.subscribe_poll = 0.2
self.subscribe_signal = 0.5
```

The constructor creates the the objects necessary for DFX API activity, including `User`, `Organization`, `Measurement`, and `websocketHandler`. Each object contains a set of API operations / endpoints related to that category. You can find out more about these objects in their `.md` files.

```python
self.user = User(server_url, firstname, lastname, email, password, gender, dateofbirth, height, weight)
self.organization = Organization(license_key, server_url)

self.ws_obj = WebsocketHandler(self.user_token, self.websocket_url)

self.measurement = Measurement(
    self.study_id, self.server_url, self.ws_obj, self.num_chunks, self.max_chunks, mode=measurement_mode, token=self.user_token)
```

The constructor also calls several internal methods to fully set up the client. These internal methods are elaborated in a section below.

`__get_urls()` gets the REST, websocket, and gRPC urls based on the server the user selects. `__measurement_mode()` handles the measurement mode selected by the user and determines the maximum number of chunks for each measurement.

```python
self.__get_urls()
self.__measurement_mode()
```

Calling the method `__setup()` performs the activities necessary for setting up the client, including register license, create user, and authentication / login. It also handles recycling and saving the values into the configuration file.

```python
self.__setup()
```

You can read more into all the private / internal methods below.

## Public Methods

### 1. `create_new_measurement`

```python
create_new_measurement(self)
```

This method makes a call to the `create` endpoint under `Measurement`, and retrieves the measurement ID from the measurement class. It then returns the `measurement_id`.

```python
try:
    self.measurement.create()
# Handling if existing token is invalid
except:
    self.__setup()
    self.measurement.create()

self.measurement_id = self.measurement.measurement_id
return self.measurement_id
```

### 2. `subscribe_to_results`

```python
async subscribe_to_results(self, token:str='', measurement_id:str='')
```

This method makes a call to the `measurement.subscribeResults` endpoint, which requests and establishes a websocket connection to receive payloads from a measurement.

It first checks for the key parameters by reading from the `.config` file. This is done in every subsequent method that involve token, measurement_id, or folder.

```python
with open(self.config_file) as json_file:
    data = json.load(json_file)
    if token == '':
        token = data[self.user.email][self.server]['user_token']

if token == '':
    raise ValueError("No user token provided. Please log in.")
if not measurement_id or measurement_id == '':
    measurement_id = self.measurement_id
```

Then it updates the some variables and creates the headers. It also generates a 10-digit request ID and sets the action ID, which are needed to make a websocket request.

```python
self.subscribe_done = False
self.sub_cycle_complete = False

# Authentication header
auth = 'Bearer ' + token
headers = {
    'Authorization': auth
}
# Randomly generated 10-digit hexdecimal request ID
requestID = uuid.uuid4().hex[:10]
actionID = '0510'
```

Now to make the actual request, we prepare the proto ( `SubscribeResultsRequest` ) and create the `data` buffer in the format `Buffer([ string:4 ][ string:10 ][ string/buffer ])`. It makes a call to the `measurement.subscribeResults` endpoint to subscribe to one measurement.

However, for cases where multiple consecutive measurements are needed (since each measurement is limited to 120 seconds long (for discrete measurement mode), any longer measurement must be represented as multiple measurements), a while loop is needed to subscribe to consecutive measurements until all data has been received.

```python
chunk_no = 0
while True:
    # Parse request data to proto object
    if not self.sub_cycle_complete:
        request = SubscribeResultsRequest()
        paramval = request.Params
        paramval.ID = measurement_id	# Updates measurement ID
        request.RequestID = requestID

        data = f'{actionID:4}{requestID:10}'.encode() + request.SerializeToString()
        done, count = await self.measurement.subscribeResults(data, chunk_num=chunk_no, queue=self.received_data)
    else:
        await asyncio.sleep(self.subscribe_poll)    # For polling
        if self.measurement_id != measurement_id:
            measurement_id = self.measurement_id
        continue

    self.sub_cycle_complete = True  # Signal that this cycle is complete

    if done:       # If all results have been received, stop the process / cycles
        break
    else:
        chunk_no += count
        await asyncio.sleep(self.subscribe_signal)    # Need to give time to signal

self.subscribe_done = True  # Signal that the entire process is done
await self.__handle_exit()
```

### 3. `add_chunk`

```python
async add_chunk(self,
                chunk:libdfx.Payload,
                token:str='',
                measurement_id:str=''
                )
```

This method adds one payload chunk to a measurement, by passing in the chunk as a `libdfx.Payload` object.

```python
# Update status
self.addData_done = False

# Extract payload elements
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
```

It then sets the `action` depending on the chunk order, and reads from the properties using different names under different DFX SDK versions.

```python
chunk_num = chunk.chunk_number
self.num_chunks = chunk.num_chunks

# Get chunk order
if chunk_num == 0 and self.num_chunks > 1:
    action = 'FIRST::PROCESS'
elif chunk_num == self.num_chunks - 1:
    action = 'LAST::PROCESS'
else:
    action = 'CHUNK::PROCESS'

# Handle dfx sdk version
chunkOrder = properties['chunk_number']
startTime = properties['start_time_s']
endTime = properties['end_time_s']
duration = properties['duration_s']
```

Depending on whether the user selected to use `websocket` or `REST`, the method prepares the websocket connection or the header, makes a call to the `measurement.add_data_ws` or the `measurement.add_data_rest` endpoint, gets the response, and decodes it.

```python
# Websockets
if self.conn_method == "websocket" or self.conn_method == "ws":
    if self.ws_obj.ws == None:
        await self.ws_obj.connect_ws()
    response = await self.measurement.add_data_ws(
        measurement_id, chunkOrder, action, startTime, endTime, duration, payload, meta)
    if response:
        status = response[10:13].decode('utf-8')    # Decode results
        body = response.decode('utf-8')
    else:
        self.addData_done = True
# REST
else:
    response = await self.measurement.add_data_rest(
        measurement_id, chunkOrder, action, startTime, endTime, duration, payload, meta)
    status = response.status_code                   # Decode results
    body = response.json()
```

Then it handles several types of errors. Since addData times out after 120s for each measurement, when that happens, it makes a call to an internal method `__handle_ws_timeout`. If timeout occurs earlier than 120s, or if there is another type of error, the addData process would stop by setting `self.addData_done = True`.

```python
if int(status) != 200:
    if int(status) == 400 or int(status) == 405:
        if chunk_num * duration < 120 and chunk_num != 0:     # Timed out earlier than 120s
            self.addData_done = True
            print("\nAdd data timed out early. Make sure there is only one active measurement under this license.")

        if self.conn_method == "websocket" or self.conn_method == "ws":
            if 'MEASUREMENT_CLOSED' in body:
                await self.__handle_ws_timeout(
                    chunkOrder, action, startTime, endTime, duration, payload, meta)
            else:
                self.addData_done = True
                print("Cannot add data to this measurement.")
        else:
            if body['Code'] == 'MEASUREMENT_CLOSED':
                await self.__handle_ws_timeout(
                    chunkOrder, action, startTime, endTime, duration, payload, meta)
            else:
                self.addData_done = True
                print("Cannot add data to this measurement.")
    else:
        self.addData_done = True
        print("Cannot add data to this measurement.")
```

Finally, the program sleeps for the chunk duration as the data gets sent. It then closes the websocket connection if all websocket processes are complete.

```python
await asyncio.sleep(duration)
await self.__handle_exit()
```

### 4. `retrieve_results`

```python
retrieve_results(self, token:str='', measurement_id:str='')
```

This method makes a call to the `measurement.retrieve` endpoint to get results to a given measurement.

```python
res = self.measurement.retrieve(token, measurement_id)
return res
```

### 5. `clear`

```python
clear(self)
```

This method clears cached user data in the `.config` file.

```python
with open(self.config_file, mode='w') as f:
    data = {}
    d = json.dumps(data)
    f.write(d)
```

It is needed when a new user must be created, since otherwise the SimpleClient would keep reusing the information from the cached user.

### 6. `shutdown`

```python
async shutdown(self)
```

This method gracefully shuts down the simpleclient object when called.

```python
self.measurement.end = True
self.addData_done = True
await asyncio.sleep(self.subscribe_signal)      # For signalling
await self.ws_obj.handle_close()
```

It simply toggles two flags and signals them so the processes can finish. Then it closes the websocket.

## Private / Internal Methods

### 1. `__get_urls`

```python
__get_urls(self)
```

This method determines the REST, websocket, and gRPC urls based on the server the user selects during initialization.

```python
self.__valid_servers = {
    "qa": {
        "server_url": "...",
        "websocket_url": "..."
    },
    "dev": {
        ...
    },
    ...
try:
    self.server_url = self.__valid_servers[self.server]["server_url"]
    self.websocket_url = self.__valid_servers[self.server]["websocket_url"]
except:
    raise ValueError("Invalid server ID given")

```

### 2. `__measurement_mode`

```python
__measurement_mode(self)
```

This method determines the maximum length of a measurement for each measurement mode given, and calculates the maximum number of chunks per measurement based on the length per chunk.

```python
self.__measurement_modes = {
    "DISCRETE": 120,
    "BATCH": 1200,
    "VIDEO": 1200,
    "STREAMING": 1200
}
try:
    max_len = self.__measurement_modes[self.measurement_mode]
except:
    raise ValueError("Invalid measurement mode given")

self.num_chunks = int(self.video_length / self.chunk_length)
self.max_chunks = int(max_len / self.chunk_length)
```


### 3. `__record`

```python
__record(self, data:dict={})
```

The method first determines if a config file is there, if not, it creates an empty one.

```python
if not self.config_file:
    self.config_file = "./default.config"

if not os.path.isfile(
        self.config_file):  
    with open(self.config_file, 'w') as f:
        d = json.dumps({})
        f.write(d)
```

This method then records all the key DFX API parameters into the `.config` file, in `json` format. Notice that the config file is in the format:

```
{
    "server1": {
        "license_key1": {
            "device_token": "...",
            "user1": {
                "user_token": "..."
            },
            "user2": {
                "user_token": "..."
            },
            ...
        },
        "license_key2": {
            ...
        },
        ...
    },
    "server2": {
        ...
    },
    ...
}
```

This structure ensures that for different servers, there can exist multiple licenses (`license_key`), which contains one `device_token` each and multiple users (identified by `user_email`), each with its own `user_token`. 

For this method, if the `data` parameter is not passed in, the new values are directly overwritten into the config file. If `data` is passed in, it creates a copy. The handling for recycling previous values are now implemented in `__setup()` below. 

```python
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
```

The next part cleans up the data dictionary, by clearing all attributes with an empty value or invalid attributes. 

```python
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
```

Finally, the data dictionary is written back into the config file.

```python
with open(self.config_file, 'w') as f:
    d = json.dumps(data)
    f.write(d)
```


### 4. `__setup`

```python
__setup(self)
```

This method handles the registration and authentication for the DFX API, as well as recycling and recording the values in the `.config` file. To call any DFX API method, an API token is required, and this method helps retrieve such a token.

The method first determines if a config file is there, if not, it creates an empty one.

```python
if not self.config_file:
    self.config_file = "./default.config"

if not os.path.isfile(
        self.config_file):
    with open(self.config_file, 'w') as f:
        json.dump({}, f)
```

Then it opens the `.config` file and goes through the parameters. First, it records the `server` ID, `license_key`, and `user_email` if they don't exist.

```python
if (self.server not in data.keys() or data[self.server] == {}):
    data[self.server] = {}

if (self.license_key not in data[self.server].keys() 
or data[self.server][self.license_key] == {}):
    data[self.server][self.license_key] = {}

if self.user.email not in data[self.server][self.license_key].keys():
    data[self.server][self.license_key][self.user.email] = {}
```

Next, for the device token, if a `device_token` doesn't exist for this server and license, it calls the `Organization.registerLicense()` endpoint to obtain a device token. On the other hand, if the device token already exists, it takes the existing token to prevent redundantly registering the same license.

Note that whenever an error occurs, it saves the current state into the config file by calling `self.__record()`, to prevent redundant operations later.

```python
if ("device_token" not in data[self.server][self.license_key].keys()
or data[self.server][self.license_key]["device_token"] == ''):
    out = self.organization.registerLicense(self.device_name)
    if 'Token' not in out:
        self.__record(data=data)
        raise Exception("Registration error. Make sure your license key is valid for the selected server.")
        return

    self.device_token = out['Token']
    data[self.server][self.license_key]["device_token"] = self.device_token

elif (self.device_token == '' and
data[self.server][self.license_key]["device_token"] != ''):
    self.device_token = data[self.server][self.license_key]["device_token"]
```

Next, for the user token, if a `user_token` does not exist for the current user on this license and server, it tries to log in (`User.login()`) the user first using the device token. If cannot be logged in, it needs to create a new user (`User.create()`) before logging in. The user information and credentials are already handled in the `User` class, so it only needs to pass in the `device_token`.

This setup prevents the creation of many new users under the same email. 

```python
if ("user_token" not in data[self.server][self.license_key][self.user.email].keys()
or data[self.server][self.license_key][self.user.email]["user_token"] == ''):
    res = self.user.login(self.device_token)

    if res == "INVALID_USER":
        res = self.user.create(self.device_token)
        if res == 'INTERNAL_ERROR':
            self.__record(data=data)
            raise Exception("Cannot create new user. Check your license permissions.")
            return
        self.user_id = res
        res = self.user.login(self.device_token)

    elif res == "INVALID_PASSWORD":
        self.__record(data=data)
        raise Exception("Incorrect login password.")
        return
    
    self.user_token = self.user.user_token

    if self.user_token != '':
        data[self.server][self.license_key][self.user.email]["user_token"] = self.user_token
else:
    self.user_token = data[self.server][self.license_key][self.user.email]["user_token"]
    self.user.user_token = self.user_token
```

Finally, we record the complete data into the config file.

```python
self.__record(data=data)
```


### 5. `__handle_ws_timeout`

```python
async __handle_ws_timeout(self,
                          headers:str,
                          chunkOrder:str,
                          action:str,
                          startTime:str,
                          endTime:str,
                          duration:str,
                          payload:bin,
                          meta:str
                         )
```

This method handles the case where a measurement times out during `addData` after 120s, while there are more payload chunks to be added. This is a design of the DFX API to prevent having too much data in one measurement. In this case, a new measurement would need to be created, and both `addData` and `subscribe_to_results` must be switched onto the new measurement.

First, it polls to check if `subscribe_to_results` from the previous measurement is complete. It can only move on once that is complete.

```python
while not self.sub_cycle_complete:  # Poll until subscribe is complete
    await asyncio.sleep(self.subscribe_poll)        # For polling
```
Once complete, we retrieve the results from the previous measurement.

```python
res = self.retrieve_results()
print(res)
```

A new measurement is then created, and the subscribe signal is changed and signalled to allow subscribe to continue on the new measurement.

```python
self.measurement_id = self.create_new_measurement()
self.sub_cycle_complete = False
await asyncio.sleep(self.subscribe_signal)
```

Finally, the last chunk that did not get added to the previous measurement is now added to the new measurement.

```python
if self.conn_method == "websocket" or self.conn_method == "ws":
    response = await self.measurement.add_data_ws(
        self.measurement_id, chunkOrder, action, startTime, endTime, duration, payload, meta)
    status = response[10:13].decode('utf-8')
    body = response.decode('utf-8')
else:
    response = await self.measurement.add_data_rest(
        self.measurement_id, chunkOrder, action, startTime, endTime, duration, payload, meta)
    status = response.status_code
    body = response.json()
```

### 6. `__handle_exit`

```python
async __handle_exit(self)
```

This method is called when exiting the simpleclient. It checks the flags to make sure all processes (add data and subscribe to results) are complete before closing the websocket connection.

```python
if not self.complete:
    if self.addData_done and self.subscribe_done:
        if self.conn_method == "websocket" or self.conn_method == "ws":
            await self.ws_obj.handle_close()
    self.complete = True
```