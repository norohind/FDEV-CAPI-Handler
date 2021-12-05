import os

import requests
from os import getenv

CLIENT_ID = getenv('client_id')
assert CLIENT_ID, "No client_id in env"

log_level = 'DEBUG'

access_key = os.getenv('access_key')

REDIRECT_URL = requests.utils.quote("http://127.0.0.1:9000/fdev-redirect")
AUTH_URL = 'https://auth.frontierstore.net/auth'
TOKEN_URL = 'https://auth.frontierstore.net/token'
PROPER_USER_AGENT = 'EDCD-a31-0.2'
REDIRECT_HTML_TEMPLATE = """
<!DOCTYPE HTML>
<html>
    <head>
        <meta http-equiv="refresh" content="0; url={link}">
    </head>
    <body>
        <a href="{link}">
            You should be redirected shortly...
        </a>
    </body>
</html>
"""

ADMIN_USERS_TEMPLATE = """
<!DOCTYPE HTML>
<html>
    <head>
    </head>
    <body>
        {}
    </body>
</html>
"""

ADMIN_USER_TEMPLATE = '<a href="{link}">{desc}</a>'
