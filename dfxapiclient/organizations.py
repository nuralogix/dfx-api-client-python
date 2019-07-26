import json
import requests


# 7
class Organization:
    def __init__(self, license_key, server_url):
        self.license_key = license_key
        self.server_url = server_url

    # 705
    def registerLicense(self, device_name):
        # [ 705, "1.0", "POST", "registerLicense", "/organizations/licenses" ],

        values = {
            "Key": self.license_key,
            "DeviceTypeID": "LINUX",
            "Name": device_name,
            "Identifier": "DFXCLIENT",
            "Version": "1.0.0"
        }
        values = json.dumps(values)

        headers = {'Content-Type': 'application/json'}

        uri = self.server_url + '/organizations/licenses'
        r = requests.post(uri, data=values, headers=headers)
        return r.json()

    # 713
    def createUser(self, api_token, data):
        # [ 713, "1.0", "POST", "createUser", "/organizations/users" ],
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
        values = {}
        for key, val in data:
            values[key] = str(val)

        values = json.dumps(values)

        auth = 'Bearer ' + api_token
        header = {'Content-Type': 'application/json', 'Authorization': auth}

        uri = self.server_url + '/organizations/users'
        r = requests.post(uri, data=values, headers=header)
        print(r.json())
        return r.json()

    # 717
    def login(self, api_token, email, pw, orgID):
        # [ 717, "1.0", "POST", "login", "/organizations/auth" ],
        values = {"Email": email, "Password": pw, "Identifier": orgID}

        header = {'Content-Type': 'application/json'}

        uri = self.server_url + '/organizations/auth'
        r = requests.post(uri, data=values, headers=header)
        print(r.json())
        return r.json()
