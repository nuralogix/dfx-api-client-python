# User

This is the class definition for the `User` class, a set of DFX API methods / endpoints for handling user activity, such as creating a user, login, get role, and retrieve user data.

*This method is currently incomplete and more endpoints will be added in subsequent updates.*

The User object depends on the following packages:

```python
import json
import requests     # Python REST requests library
```

## Constructor

```python
__init__(self,
         url:str,
         firstname:str,
         lastname:str,
         email:str,
         password:str,
         phonenum:str='',
         gender:str='',
         dateofbirth:str='',
         height:str='',
         weight:str=''
        )
```

The constructor takes in these parameters in `string` format, and stores them in a dictionary called `self.user_data`.

## Methods

Notes:

* The indexing is based on a summary of endpoints from the DFX API.
* All endpoints require an API token (can be a user token or device token) and a REST server url (e.g. `https://api.deepaffex.ai:9443`).

### 0. `create`

```python
create(self, api_token:str)
```

This endpoint creates a user given their information, using a REST `post` request. This information is taken from `self.user_data`, which is generated from the constructor.

```python
values = json.dumps(self.user_data)

auth = 'Bearer ' + api_token
header = {
    'Content-Type': 'application/json',
    'Authorization': auth
}

uri = self.url + '/users'
r = requests.post(uri, data=values, headers=header)
res = r.json()
if 'ID' not in res:
    print(res)
    raise Exception('Cannot create user')

self.user_id = res['ID']
return self.user_id
```

### 1. `login`

```python
login(self, api_token:str)
```

This endpoint logs in a user given their email and password, using a REST `post` request. This information is taken from the constructor.

```python
values = {}
values["Email"] = str(self.email)
values["Password"] = str(self.password)

values = json.dumps(values)

auth = 'Bearer ' + api_token
header = {
    'Content-Type': 'application/json',
    'Authorization': auth
}

uri = self.url + '/users/auth'
r = requests.post(uri, data=values, headers=header)
res = r.json()

if 'Token' not in res:
    raise Exception('User not found')

self.user_token = res['Token']
return self.user_token
```

### 2. `retrieve`

```python
retrieve(self)
```

This endpoint retrieves user data by through a REST `get` request.

```python
uri = self.url + '/users'
r = requests.get(uri, headers=self.header)
return r.json()
```

### 6. `remove`

```python
remove(self)
```

This endpoint deletes a user through a REST `delete` request.

```python
uri = self.url + '/users'
r = requests.delete(uri, headers=self.header)
return r.json()
```

### 11. `getRole`

```python
getRole(self, api_token:str, url:str)
```

This endpoints gets the role of a user through a REST `get` request.

```python
uri = self.url + '/users/role'
r = requests.get(uri, headers=self.header)
return r.json()
```
