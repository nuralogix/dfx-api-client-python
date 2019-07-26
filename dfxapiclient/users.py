import json
import requests


# 2
class User:
    def __init__(self,
                 url,
                 firstname,
                 lastname,
                 email,
                 password,
                 phonenum='',
                 gender='',
                 dateofbirth='',
                 height='',
                 weight=''):
        self.firstname = firstname
        self.lastname = lastname
        self.email = email
        self.password = password
        self.phonenum = phonenum
        self.gender = gender
        self.dateofbirth = dateofbirth
        self.height = height
        self.weight = weight

        self.user_data = {}
        self.user_data["FirstName"] = firstname
        self.user_data["LastName"] = lastname
        self.user_data["Email"] = email
        self.user_data["Password"] = password
        self.user_data["PhoneNumber"] = phonenum
        self.user_data["Gender"] = gender
        self.user_data["DateOfBirth"] = dateofbirth
        self.user_data["HeightCm"] = height
        self.user_data["WeightKg"] = weight

        self.user_id = ''
        self.user_token = ''
        self.url = url
        self.header = ''

    def __update_token(self, token):
        self.token = token
        auth = 'Bearer ' + token
        self.header = {'Content-Type': 'application/json', 'Authorization': auth}

    # 200
    def create(self, api_token):
        # [ 200, "1.0", "POST", "create", "/users" ]
        '''
        Data format:

        values = """
          {
            "FirstName": "John",
            "LastName": "Appleseed",
            "Email": "john@example.com",
            "Password": "testpassword",
            "Gender": "male",
            "DateOfBirth": "1986-02-10",
            "HeightCm": "180",
            "WeightKg": "70"
          }
        """
        '''
        values = json.dumps(self.user_data)

        auth = 'Bearer ' + api_token
        header = {'Content-Type': 'application/json', 'Authorization': auth}

        uri = self.url + '/users'
        r = requests.post(uri, data=values, headers=header)
        res = r.json()
        if 'ID' not in res:
            print(res)
            return

        self.user_id = res['ID']
        return self.user_id

    # 201
    def login(self, api_token):
        # [ 201, "1.0", "POST", "login", "/users/auth" ]

        values = {}
        values["Email"] = str(self.email)
        values["Password"] = str(self.password)

        values = json.dumps(values)

        auth = 'Bearer ' + api_token
        header = {'Content-Type': 'application/json', 'Authorization': auth}

        uri = self.url + '/users/auth'
        r = requests.post(uri, data=values, headers=header)
        res = r.json()

        if 'Token' not in res:
            raise Exception('User not found')

        self.user_token = res['Token']
        self.__update_token(self.user_token)
        return self.user_token

    # 202
    def retrieve(self):
        # [ 202, "1.0", "GET", "retrieve", "/users" ]
        uri = self.url + '/users'
        r = requests.get(uri, headers=self.header)
        print(r.json())
        return r.json()

    # 206
    def remove(self):
        # [ 206, "1.0", "DELETE", "remove", "/users" ]
        uri = self.url + '/users'
        r = requests.delete(uri, headers=self.header)
        print(r.json())
        return r.json()

    # 211
    def getRole(self):
        # [ 211, "1.0", "GET", "getRole", "/users/role" ]
        uri = self.url + '/users/role'
        r = requests.get(uri, headers=self.header)
        print(r.json())
        return r.json()
