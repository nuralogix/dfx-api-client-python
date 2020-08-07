**This library is now retired in favour of the new [dfx-apiv2-client-py](https://github.com/nuralogix/dfx-apiv2-client-py).**

# DFX API Python SimpleClient

The DFX API Python SimpleClient simplifies access to the DeepAffex API.

This client contains basic functionality, including:

* Registering a device
* Creating a user
* User login
* Creating a measurement
* Subscribing to results
* Adding measurement data
* Retrieving results

## Requirements

Python 3.6 and above is required. On Windows, simply install the latest version of Python. On Ubuntu, type the following into a terminal:

```bash
sudo apt-get install python3.6 python3.6-venv
```

**Note:**
Do not add data or subscribe to results to an international server as it will create problems due to latency and other issues. For example, if you are in North America (Canada or USA), do not connect to a Chinese server (or vice versa). This will eventually be handled in subsequent updates.

## Available Methods

Here is a list of all public methods and descriptions for `class SimpleClient`:

### Constructor

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

* Creates a SimpleClient object
* Registers license, creates a user and logs in the user
* Caches current user information (in 'default.config')
* Does not create new user or login user if user is already logged in
* `server` specifies the API server used; it can be `qa`, `dev`, `prod`, `demo`, `demo-cn`, `prod-cn`
* `add_method` specifies what type of connection is used, `REST` or `websocket`
* `measurement_mode` can only be `DISCRETE`, `STREAMING`, `BATCH`, and `VIDEO`
* All variables here must be in `string` format

### `create_new_measurement`

```python
create_new_measurement(self)
```

* Creates a new measurement using REST. Returns the measurement ID
* Most recent measurement ID is cached

### `subscribe_to_results`

```python
async subscribe_to_results(self, token:str='', measurement_id:str='')
```

* Establishes a websocket connection to receive results to a measurement
* Default: on the last measurement created (in the cache); Provide the `measurement_id` for any other measurement
* Disconnects following the last data chunk received
* Records received data in the specified folder (the `receive_folder` element in `__init__` if not specified here). If no `receive_folder` is specified, then it does not save the received data locally
* The results are stored in memory in an async queue (`asyncio.Queue`) called `self.received_data`. Call the method `self.received_data.get()` to retrieve a chunk result.
* Need to be called in an *async event loop* or be `await`ed

### `add_chunk`

```python
async add_chunk(self, chunk:libdfx.Payload, token:str='', measurement_id:str='')
```

* Establishes a a REST or websocket connection to add data to a measurement
* User can select what type of connection will be used with the parameter `conn_method` at the constructor
* Sends the payload chunk passed into this method. `chunk` must be a `libdfx.Payload` object, generated from the DFX SDK
* Default: on the last measurement created (in the cache); Provide the `measurement_id` for any other measurement
* Need to be called in an *async event loop* or be `await`ed
* Check `dfx-sdk-example` (`dfxexample.py`) for sample usage

### `retrieve_results`

```python
retrieve_results(self, token:str='', measurement_id:str='')
```

* Retrieves results from a measurement using REST
* Default: on the last measurement created (in the cache); Provide the `measurement_id` for any other measurement

### `clear`

```python
clear(self)
```

* Clears cached user data
* Needed when a new user must be created

### `shutdown`

```python
async shutdown(self)
```

* Gracefully handles a sudden shutdown of all processes
* Need to be called in an *async event loop* or be `await`ed

### Constraints:

* When using addData and subscribe_to_results, all payload chunks must be of the same duration except for the last one.
* Payload chunks must have a duration between 5 and 30 seconds, inclusive.

For a more detailed documentation of the DFX API SimpleClient, go to `simpleclient.md` under `/dfxapiclient`.
