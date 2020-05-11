import json

import requests


# 7
class Organization:
    """`Organization` is for handling activity for an organization.

    This class handles registering a license, creating a user within an organization, and
    logging in an organization.

    https://dfxapiversion10.docs.apiary.io/#reference/0/organizations

    *Currently incomplete and more endpoints will be added in subsequent updates.*
    """
    def __init__(self, license_key: str, server_url: str):
        """[summary]

        Arguments:
            license_key {str} -- DFX API license key
            server_url {str} -- DFX API REST server URL
        """
        self.license_key = license_key
        self.server_url = server_url

    # 705
    def registerLicense(self, device_name: str):
        """Register a license given a DFX API license key and a device name
        in `string` format, using a REST `post` request.
        https://dfxapiversion10.docs.apiary.io/#reference/0/organizations/register-license

        Arguments:
            device_name {str} -- Device name

        Returns:
            {str} -- JSON encoded response
        """
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
    def createUser(self, api_token: str, data: dict):
        """Create a user with the current organization given user data using a POST.
        https://dfxapiversion10.docs.apiary.io/#reference/0/organizations/create-user

        Arguments:
            api_token {str} -- DFX API token
            data {dict} -- User data

        Returns:
            {str} -- JSON encoded response
        """
        # [ 713, "1.0", "POST", "createUser", "/organizations/users" ],
        # Data format:
        # values = """
        # {
        #     "FirstName": "John",
        #     "LastName": "Appleseed",
        #     "Email": "john@example.com",
        #     "Password": "testpassword",
        #     "Gender": "male",
        #     "DateOfBirth": "1986-02-10",
        #     "HeightCm": "180",
        #     "WeightKg": "70"
        # }
        values = {}
        for key, val in data:
            values[key] = str(val)

        values = json.dumps(values)

        auth = 'Bearer ' + api_token
        header = {'Content-Type': 'application/json', 'Authorization': auth}

        uri = self.server_url + '/organizations/users'
        r = requests.post(uri, data=values, headers=header)
        return r.json()

    # 717
    def login(self, api_token, email, pw, orgID):
        """Login into an organization using a POST.
        https://dfxapiversion10.docs.apiary.io/#reference/0/organizations/login

        Arguments:
            api_token {str} -- DFX token
            email {str} -- Email address
            pw {str} -- Password
            orgID {str} -- Organisation ID

        Returns:
            str -- JSON encoded response
        """
        # [ 717, "1.0", "POST", "login", "/organizations/auth" ],
        values = {"Email": email, "Password": pw, "Identifier": orgID}

        auth = 'Bearer ' + api_token
        header = {'Content-Type': 'application/json', 'Authorization': auth}

        uri = self.server_url + '/organizations/auth'
        r = requests.post(uri, data=values, headers=header)
        return r.json()
