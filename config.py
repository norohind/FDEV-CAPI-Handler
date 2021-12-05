import os

import requests
from os import getenv

CLIENT_ID = getenv('client_id')
assert CLIENT_ID, "No client_id in env"

log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()

access_key = os.getenv('access_key')

REDIRECT_URL = requests.utils.quote(os.getenv('REDIRECT_URL'))
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
