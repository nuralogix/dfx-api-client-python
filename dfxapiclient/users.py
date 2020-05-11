import json

import requests


# 2
class User:
    """`User` is for handling user activity

    This class handles creating a user, login, getting role, and retrieving user data.

    https://dfxapiversion10.docs.apiary.io/#reference/0/users

    *Currently incomplete and more endpoints will be added in subsequent updates.*
    """
    def __init__(self,
                 url: str,
                 firstname: str,
                 lastname: str,
                 email: str,
                 password: str,
                 phonenum: str = '',
                 gender: str = '',
                 dateofbirth: str = '',
                 height: str = '',
                 weight: str = ''):
        """Create a User object

        Arguments:
            url {str} -- URL to connect to
            firstname {str} -- First name
            lastname {str} -- Last name
            email {str} -- Email address
            password {str} -- Password

        Keyword Arguments:
            phonenum {str} -- Phone number (default: {''})
            gender {str} -- Gender (default: {''})
            dateofbirth {str} -- Date of birth (default: {''})
            height {str} -- Height (cm) (default: {''})
            weight {str} -- Weight (kg) (default: {''})
        """
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
    def create(self, api_token: str):
        """Create a user using POST. Information is taken from `self.user_data`,
        which is generated from the constructor.
        https://dfxapiversion10.docs.apiary.io/#reference/0/users/create

        Arguments:
            api_token {str} -- DFX token

        Returns:
            str -- User ID
        """
        # [ 200, "1.0", "POST", "create", "/users" ]
        # Data format:
        # values = """
        #   {
        #     "FirstName": "John",
        #     "LastName": "Appleseed",
        #     "Email": "john@example.com",
        #     "Password": "testpassword",
        #     "Gender": "male",
        #     "DateOfBirth": "1986-02-10",
        #     "HeightCm": "180",
        #     "WeightKg": "70"
        #   }
        # """
        values = json.dumps(self.user_data)

        auth = 'Bearer ' + api_token
        header = {'Content-Type': 'application/json', 'Authorization': auth}

        uri = self.url + '/users'
        r = requests.post(uri, data=values, headers=header)
        res = r.json()
        if 'ID' not in res:
            return res['Code']

        self.user_id = res['ID']
        return self.user_id

    # 201
    def login(self, api_token: str):
        """Login using POST. Information is taken from `self.user_data`,
        which is generated from the constructor.
        https://dfxapiversion10.docs.apiary.io/#reference/0/users/login

        Arguments:
            api_token {str} -- Device token

        Returns:
            str -- User token
        """
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
            return res['Code']

        self.user_token = res['Token']
        self.__update_token(self.user_token)
        return self.user_token

    # 202
    def retrieve(self):
        """Retrieve user data using a GET.
        https://dfxapiversion10.docs.apiary.io/#reference/0/users/retrieve

        Returns:
            str -- JSON encoded user data
        """
        # [ 202, "1.0", "GET", "retrieve", "/users" ]
        uri = self.url + '/users'
        r = requests.get(uri, headers=self.header)
        return r.json()

    # 206
    def remove(self):
        """Remove a user using a DELETE
        https://dfxapiversion10.docs.apiary.io/#reference/0/users/remove

        Returns:
            str -- JSON encoded response
        """
        # [ 206, "1.0", "DELETE", "remove", "/users" ]
        uri = self.url + '/users'
        r = requests.delete(uri, headers=self.header)
        return r.json()

    # 211
    def getRole(self):
        """Get the role of a user using a GET
        https://dfxapiversion10.docs.apiary.io/#reference/0/users/retrieve-user-role

        Returns:
            str -- JSON encoded role
        """
        # [ 211, "1.0", "GET", "getRole", "/users/role" ]
        uri = self.url + '/users/role'
        r = requests.get(uri, headers=self.header)
        return r.json()
