# Measurement

This is the class definition for the `Measurement` class, a set of DFX API methods / endpoints for handling measurement activity, including creating a measurement, add data, subscribe to results, and retrieve results.

*This method is currently incomplete and more endpoints will be added in subsequent updates.*


The Measurement object depends on the following packages:

```python
# Python dependancies
import asyncio
import base64
import json
import requests
import time
import uuid
import websockets
from google.protobuf.json_format import ParseDict

# Other objects from this library
from .websocketHelper import WebsocketHandler

# Complied proto files for websocket requests
from .measurements_pb2 import DataRequest, SubscribeResultsRequest
```

## Constructor

```python
__init__(self,
         study_id:str,
         rest_url:str,
         ws_obj:WebsocketHandler,
         num_chunks:int,
         max_chunks:int,
         mode:str='DISCRETE',
         token:str='',
         usrprofileID:str=''
        )
```

The constructor takes in these parameters in `string` format, except for ws_obj, which must be a `WebsocketHandler` object. It also sets up the REST header as `self.header`. By default, the measurement mode is `DISCRETE`.

## Methods

Notes:

* The indexing is based on a summary of endpoints from the DFX API.

### 0. `retrieve`

```python
retrieve(self, token:str, measurement_id:str)
```

This endpoint retrieves the results for a given measurement (by `measurement_id`) through a REST `get` request.

```python
if not measurement_id:
    measurement_id = self.measurement_id
if not measurement_id or measurement_id == '':
    raise ValueError("No measurement ID given")

uri = self.url + '/measurements/' + self.measurement_id
r = requests.get(uri, headers=self.header)
return r.json()
```

### 4. `create`

```python
create(self)
```

This endpoint creates a new measurement, through a REST `post` request, provided with a valid `study_id` from the constructor class. It then saves and returns the `measurement_id`.

```python
values = {
    "StudyID": self.study_id,
    "Resolution": 100,
    "UserProfileID": self.profile_id,
    "Mode": self.mode
}
values = json.dumps(values)

uri = self.url + '/measurements'
r = requests.post(uri, data=values, headers=self.header)
res = r.json()

if 'ID' not in res:
    print(res)
    raise Exception("Cannot create measurement")

self.measurement_id = res['ID']
return self.measurement_id
```

### 6a. `add_data_rest`

```python
async add_data_rest(self,
                    measurement_id:str,
                    chunkOrder:str,
                    action:str,
                    startTime:str,
                    endTime:str,
                    duration:str,
                    payload:bin,
                    meta:dict={}
                   )
```

This method formats and adds one payload chunk to the measurement using a REST `post` request, given all the payload information. The data is sent in a Python `dictionary` format, stringfied to json.

```python
uri = self.url + "/measurements/" + measurement_id + "/data"    # Form a custon REST url

# Put all data into a dictionary format
data = {}
data["ChunkOrder"] = chunkOrder
data["Action"]     = action
data["StartTime"]  = startTime
data["EndTime"]    = endTime
data["Duration"]   = duration
# Additional meta fields !
meta['Order'] = chunkOrder
meta['StartTime'] = startTime
meta['EndTime'] = endTime
meta['Duration'] = data['Duration']
data['Meta'] = json.dumps(meta)
data["Payload"] = base64.b64encode(payload).decode('utf-8') # Payload has to be encoded to base 64

result = requests.post(uri, data=json.dumps(data), headers=self.header)  # Make the request
return result
```

### 6b. `add_data_ws`

```python
async add_data_ws(self,
                  measurement_id:str,
                  chunkOrder:str,
                  action:str,
                  startTime:str,
                  endTime:str,
                  duration:str,
                  payload:bin,
                  meta:dict={}
                 )
```

This method formats and adds one payload chunk to the measurement using a websocket connection, given all the payload information. It sends the data and awaits for a response. All the websocket interaction is done with a `WebsocketHandler` object `self.ws_obj`.

The data format must be a `DataRequest` protocol buffer (protobuf), then combined with a 10-digit `requestID` and 4-digit `actionID` to get the format `Buffer( [ string:4 ][ string:10 ][ string/buffer ] )`, before it could be sent.

```python
data = DataRequest()        # Proto data format for add data request
paramval = data.Params
paramval.ID = measurement_id

data.ChunkOrder = chunkOrder
data.Action     = action
data.StartTime  = startTime
data.EndTime    = endTime
data.Duration   = duration
# Additional meta fields !
meta['Order'] = chunkOrder
meta['StartTime'] = startTime
meta['EndTime'] = endTime
meta['Duration'] = data.Duration
data.Meta = json.dumps(meta).encode()
data.Payload = bytes(payload)		# Payload has to be encoded to base 64

requestID = uuid.uuid4().hex[:10]   # Randomly generated 10-digit hexdecimal request ID
actionID = '0506'   # Action ID of the endpoint (see DFX API documentation Section 3.6)
data = f'{actionID:4}{requestID:10}'.encode() + data.SerializeToString()

await self.ws_obj.handle_send(data) # Send data
```

To receive a response, polling must be done (using a `while` loop), since otherwise there could be a deadlock if nothing is being received (the program will get stuck / blocked at receive). By using `await asyncio.wait_for`, it also allows context switching in the asyncio event loop while polling for the result.

```python
while True:
    if not self.end:        # For handling early exit
        try:
            await asyncio.wait_for(self.ws_obj.handle_recieve(), timeout=self.recv_timeout)
        except:
            if self.end:
                break
            else:
                continue
        if self.ws_obj.addDataStats:
            response = self.ws_obj.addDataStats[0]
            self.ws_obj.addDataStats = self.ws_obj.addDataStats[1:]
            break
    else:           # If there is an early exit
        return
return response
```

### 10. `subscribeResults`

```python
async subscribeResults(self, data:bytes, chunk_num:int=0, queue:asyncio.Queue=None)
```

This method creates a constant websocket connection to receive the sent payload chunks to a given measurement, and stops once all the chunks have been received. It saves the results in a local folder if provided. All the websocket interaction is done with a `WebsocketHandler` object `self.ws_obj`.

It first sends the `data` buffer to the websocket to make the initial subscribe request. Then, to determine when to stop subscribing, the number of chunks need to be calculated. This takes into consideration that a maximum of 120s of data can be sent to one measurement at a time. The limit can therefore be calculated given the chunk duration, and is stored in `self.max_chunks`. `self.chunks_rem` keeps track of the number of remaining chunks.

```python
if self.ws_obj.ws == None:      # Create websocket connection if not connected
    await self.ws_obj.connect_ws()
await self.ws_obj.handle_send(data)     # Send initial subscribe request

done = False
counter = chunk_num
if self.chunks_rem < 0:
    raise ValueError("Invalid number of chunks")

# Calculate the number of iterations (chunks)
if self.chunks_rem > self.max_chunks:
    num_limit = chunk_num + self.max_chunks
    self.chunks_rem -= self.max_chunks
else:
    num_limit = chunk_num + self.chunks_rem
    self.chunks_rem = 0
```

In the main loop, in each iteration a response is received from the websocket. The response can either be a confirmation status, or can be a payload chunk. This is already sorted out by `ws_obj.handle_recieve()` into two stacks, `ws_obj.subscribeStats` for statuses, and `ws_obj.chunks` for payload chunks.

```python
while counter < num_limit:
    if not self.end:        # For handling early exit
        try:
            await self.ws_obj.handle_recieve()
        except:
            if self.end:
                break
            else:
                continue

        if self.ws_obj.subscribeStats:      # If response is a confirmation status
            response = self.ws_obj.subscribeStats[0]
            self.ws_obj.subscribeStats = self.ws_obj.subscribeStats[1:]
            statusCode = response[10:13].decode('utf-8')
            print("Status:", statusCode)
            if statusCode != '200':
                raise Exception("Unable to make a subscribe request. Please check your measurement ID.")

        elif self.ws_obj.chunks:            # If response is a payload chunk
            counter += 1
            response = self.ws_obj.chunks[0]
            self.ws_obj.chunks = self.ws_obj.chunks[1:]
            _id = response[0:10].decode('utf-8')
            print("--------------------------")
            print("Data received; Chunk: "+str(counter) +
                    "; Status: "+str(statusCode))

            # Store results in queues
            await self.received_data.put(response[13:])
            if queue:
                await queue.put(response[13:])

    else:           # If there is an early exit
        done = True
        return done, counter
```

After this iteration is done, a boolean status `done` and the `counter` are returned. This enables another call of `subscribe_to_results` if multiple measurements were created and not all data has been received yet.

```python
if self.chunks_rem > 0:
    done = False
else:
    done = True

return done, counter
```
