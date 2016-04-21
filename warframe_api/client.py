import json
import time
import requests

from functools import wraps

from .whirlpool import Whirlpool

class LoginError(Exception):
    def __init__(self, text, code):
        self.text = text
        self.code = code

    def __str__(self):
        return self.text

class NotLoggedInException(Exception):
    pass

class AlreadyLoggedInException(LoginError):
    def __init__(self):
        super().__init__('Already logged in', 409)

class VersionOutOfDateException(LoginError):
    def __init__(self):
        super().__init__('Version out of date', 400)

def login_required(func):
    @wraps(func)
    def wrap(self, *args, **kwargs):
        if not self._session_data:
            raise NotLoggedInException()

        return func(self, *args, **kwargs)
    return wrap

class Client():
    def __init__(self, email, password):
        self._email = email
        self._password_hash = Whirlpool(password).hexdigest()
        self._session_data = {}

    def _post_message(self, url, data):
        headers={
            # This is the Android app's ID. Doesn't seem to be necessary.
            #'X-Titanium-Id': '9bbd1ddd-f7f2-402d-9777-873f458cb50c',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': '',
        }

        r = requests.post(url, data=data, headers=headers)
        r.raise_for_status()
        return r.json()

    def login(self):
        url = 'https://api.warframe.com/API/PHP/login.php'

        # While most data is form-encoded, login data is sent as JSON for some reason...
        data = json.dumps({
            'email': self._email,
            'password': self._password_hash,
            'time': int(time.time()),

            # This seems to be based on the phone's device ID.
            # Not sure how it's used, but it is required.
            'date': 9999999999999999,

            # mobile=True prevents clobbering an active player's session.
            'mobile': True,

            # Taken from the Android app.
            'appVersion': '4.1.2.4',
        }, separators=(',', ':')) # Compact encoding.

        try:
            login_info = self._post_message(url, data)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                raise AlreadyLoggedInException() from e
            elif e.response.status_code == 400 and 'version out of date' in e.response.text:
                raise VersionOutOfDateException() from e
            else:
                raise LoginError(e.response.text, e.response.status_code) from e

        #print(login_info)
        self._session_data = {
            'mobile': True,
            'accountId': login_info['id'],
            'nonce': login_info['Nonce']
        }

    @login_required
    def logout(self):
        url = 'https://api.warframe.com/API/PHP/logout.php'
        self._post_message(url, self._session_data)
        self._session_data = {}

    @login_required
    def get_inventory(self):
        url = 'https://api.warframe.com/API/PHP/inventory.php'
        return self._post_message(url, self._session_data)
