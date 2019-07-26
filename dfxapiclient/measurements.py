# Python dependancies
import asyncio
import base64
import json
import requests
import uuid

# Compiled proto files for websocket requests
from .measurements_pb2 import DataRequest


# 5
class Measurement:
    def __init__(self,
                 study_id,
                 rest_url,
                 ws_obj,
                 num_chunks,
                 max_chunks,
                 mode='DISCRETE',
                 token='',
                 usrprofileID=''):
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
    def retrieve(self, measurement_id=None):
        # [ 500, "1.0", "GET", "retrieve", "/measurements/:ID" ]
        if not measurement_id:
            measurement_id = self.measurement_id
        if not measurement_id or measurement_id == '':
            raise ValueError("No measurement ID given")
        uri = self.url + '/measurements/' + self.measurement_id
        r = requests.get(uri, headers=self.header)
        print(r.json())
        return r.json()

    # 504
    def create(self):
        # [ 504, "1.0", "POST", "create", "/measurements" ]
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

    # 506
    # REST
    async def add_data_rest(self,
                            measurement_id,
                            chunkOrder,
                            action,
                            startTime,
                            endTime,
                            duration,
                            payload,
                            meta={}):
        # [ 506, "1.0", "POST", "data", "/measurements/:ID/data" ]
        uri = self.url + "/measurements/" + measurement_id + "/data"

        data = {}
        data["ChunkOrder"] = chunkOrder
        data["Action"] = action
        data["StartTime"] = startTime
        data["EndTime"] = endTime
        data["Duration"] = duration
        # Additional meta fields !
        meta['Order'] = chunkOrder
        meta['StartTime'] = startTime
        meta['EndTime'] = endTime
        meta['Duration'] = data['Duration']
        data['Meta'] = json.dumps(meta)
        # Payload has to be encoded to base 64
        data["Payload"] = base64.b64encode(payload).decode('utf-8')

        result = requests.post(uri, data=json.dumps(data), headers=self.header)
        return result

    # Websocket
    async def add_data_ws(self,
                          measurement_id,
                          chunkOrder,
                          action,
                          startTime,
                          endTime,
                          duration,
                          payload,
                          meta={}):
        data = DataRequest()
        paramval = data.Params
        paramval.ID = measurement_id

        data.ChunkOrder = chunkOrder
        data.Action = action
        data.StartTime = startTime
        data.EndTime = endTime
        data.Duration = duration
        # Additional meta fields !
        meta['Order'] = chunkOrder
        meta['StartTime'] = startTime
        meta['EndTime'] = endTime
        meta['Duration'] = data.Duration
        data.Meta = json.dumps(meta).encode()
        data.Payload = bytes(payload)  # Payload has to be encoded to base 64

        # Randomly generated 10-digit hexdecimal request ID
        requestID = uuid.uuid4().hex[:10]  # Or can use requestID = "0000000001"

        actionID = '0506'  # Action ID of the endpoint (see DFX API documentation Section 3.6)

        # Must be in the following format
        data = f'{actionID:4}{requestID:10}'.encode() + data.SerializeToString()

        await self.ws_obj.handle_send(data)
        while True:
            if not self.end:
                try:
                    await asyncio.wait_for(self.ws_obj.handle_recieve(),
                                           timeout=self.recv_timeout)
                except:
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
    async def subscribeResults(self, data, chunk_num=0, queue=None):
        # [ 510, "1.0", "CONNECT", "subscribeResults", "/measurements/:ID/results/" ]
        # print("\nSubscribing to results")
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

        while counter < num_limit:
            if not self.end:
                try:
                    await self.ws_obj.handle_recieve()
                except:
                    if self.end:
                        break
                    else:
                        continue

                if self.ws_obj.subscribeStats:
                    response = self.ws_obj.subscribeStats[0]
                    self.ws_obj.subscribeStats = self.ws_obj.subscribeStats[1:]
                    statusCode = response[10:13].decode('utf-8')
                    # print("Status:", statusCode)
                    if statusCode != '200':
                        raise Exception(
                            "Unable to make a subscribe request. Please check your measurement ID."
                        )

                elif self.ws_obj.chunks:
                    counter += 1
                    response = self.ws_obj.chunks[0]
                    self.ws_obj.chunks = self.ws_obj.chunks[1:]
                    # print("--------------------------")
                    # print("Data received; Chunk: "+str(counter) +
                    #   "; Status: "+str(statusCode))

                    # await self.received_data.put(response[13:])
                    if queue:
                        await queue.put(response[13:])

                    if len(response[13:]
                           ) < 1000:  # Print worker error message if there is any
                        print(response[13:])

            else:
                done = True
                return done, counter

        if self.chunks_rem > 0:
            done = False
        else:
            done = True

        # print("--------------------------")
        return done, counter
