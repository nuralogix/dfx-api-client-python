# Organization

This is the class definition for the `Organization` class, a set of DFX API methods / endpoints for handling activity for an organization. It includes registering a license, creating a user within an organization, and logging in an organization.

*This method is currently incomplete and more endpoints will be added in subsequent updates.*

The Organization object depends on the following packages:

```python
import json
import requests     # Python REST requests library
```

## Constructor

```python
__init__(self, license_key:str, server_url:str)
```

The constructor takes in these parameters in `string` format. `license_key` is a DFX API license key, granted by your administrator. `server_url` is a REST server url (e.g. `https://api.deepaffex.ai:9443`).

## Methods

Notes:

* The indexing is based on a summary of endpoints from the DFX API.
* Some endpoints require an API token (can be a user token or device token).

### 5. `registerLicense`

```python
registerLicense(self, device_name:str)
```

This endpoint registers a license given a DFX API license key and a device name in `string` format, using a REST `post` request.

```python
values = {
    "Key": self.license_key,
    "DeviceTypeID": "LINUX",
    "Name": device_name,
    "Identifier": "DFXCLIENT",
    "Version": "1.0.0"
}
values = json.dumps(values)

headers = {
    'Content-Type': 'application/json'
}

uri = self.server_url + '/organizations/licenses'
r = requests.post(uri, data=values, headers=headers)
return r.json()
```

### 13. `createUser`

```python
createUser(self, api_token:str, data:str)
```

This endpoint creates a user with the current organization given user data, where `data` is a dictionary. It is done using a REST `post` request.

```python
values = {}
for key, val in data:
    values[key] = str(val)

values = json.dumps(values)

auth = 'Bearer ' + api_token
header = {
    'Content-Type': 'application/json',
    'Authorization': auth
}

uri = self.server_url + '/organizations/users'
r = requests.post(uri, data=values, headers=header)
return r.json()
```

### 17. `login`

```python
login(self, api_token:str, email:str, pw:str, orgID:str)
```

This endpoint logs into an organization given the credentials of an organization (email, password, and orgID all in `string` format), using a REST `post` request.

```python
values = {
    "Email": email,
    "Password": pw,
    "Identifier": orgID
}

header = {
    'Content-Type': 'application/json'
}

uri = self.server_url + '/organizations/auth'
r = requests.post(uri, data=values, headers=header)
return r.json()
```
