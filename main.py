import base64
import hashlib
import os
import sqlite3
import time

import falcon
import requests
import waitress

import config
from config import REDIRECT_URL, AUTH_URL, TOKEN_URL, PROPER_USER_AGENT, CLIENT_ID, REDIRECT_HTML_TEMPLATE
from refresher import refresh_one_token


# import logging
# from sys import stdout


def generate_challenge(_verifier):
    """ It takes code verifier and return code challenge"""
    return base64.urlsafe_b64encode(hashlib.sha256(_verifier).digest())[:-1].decode('utf-8')


"""
# setting up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
stdout_handler = logging.StreamHandler(stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(process)d:%(thread)d: %(module)s:%(lineno)d: %(message)s')
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
"""

"""
Typical workflow:
1. User open Authorize endpoint
2. Authorize building link for FDEV's /auth, sending link to user
3. Authorize write code_verifier, state, timestamp_init to DB
4. User approving client, redirecting to FDEV_redirect endpoint
5. Searching in DB if we have record with this state
    if don't have:
        raise error for user, exit

6. Write received code to DB
7. Build Token Request
    if not success:
        remove all related info from DB
        raise error for user, exit
8. Store access_token, refresh_token, expires_in, timestamp_got_expires_in
9. Raise "all right" for user      

DB Tables:
1. authorizations
code_verifier text - store code_verifier, don't storing code_challenge because we can get it from verifier
state text - state
timestamp_init text - unix timestamp when authorization was started, can be used to count 25 days until next auth
code text - code (from frontier redirect)
access_token text - access token aka bearer
refresh_token text - refresh token
expires_in text - expires in for access token (in secs) 
timestamp_got_expires_in text - unix timestamp, when we got expires_in for access token
nickname text - nickname of tokens owner
"""

sql_conn = sqlite3.connect(database="companion-api.sqlite")
with sql_conn:
    sql_conn.execute(
        "create table if not exists authorizations (code_verifier text , state text, "
        "timestamp_init text , code text, access_token text, refresh_token text, expires_in text, "
        "timestamp_got_expires_in text, nickname text unique);")
sql_conn.close()


class Authorize:
    def on_get(self, req, resp):
        sql_connection = sqlite3.connect(database="companion-api.sqlite")
        code_verifier = base64.urlsafe_b64encode(os.urandom(32))
        code_challenge = generate_challenge(code_verifier)
        state_string = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")

        redirect_user_to = f"{AUTH_URL}?audience=all&scope=capi&response_type=code&client_id={CLIENT_ID}" + \
                           f"&code_challenge={code_challenge}&code_challenge_method=S256&state={state_string}" + \
                           f"&redirect_uri={REDIRECT_URL}"
        with sql_connection:
            sql_connection.execute(
                "insert into authorizations (code_verifier, state, timestamp_init) values "
                "(?, ?, ?);", [code_verifier.decode('utf-8'), state_string, int(time.time())])
        sql_connection.close()
        resp.content_type = falcon.MEDIA_HTML
        resp.text = REDIRECT_HTML_TEMPLATE.format(link=redirect_user_to)


class FDEV_redirect:
    def on_get(self, req, resp):
        error_id = hashlib.sha256(os.urandom(32)).hexdigest()
        code = req.get_param('code')
        state = req.get_param('state')
        if not code or not state:
            raise falcon.HTTPBadRequest(description=f"No code or no state")

        sql_connection = sqlite3.connect(database="companion-api.sqlite")
        with sql_connection:
            code_verifier = sql_connection.execute("select code_verifier from authorizations where state = ?;",
                                                   [state]).fetchone()
        if code_verifier is None:
            # Somebody got here not by frontier redirect
            raise falcon.HTTPBadRequest(description="Don't show here without passing frontier authorization!")
        code_verifier = code_verifier[0]

        with sql_connection:
            sql_connection.execute("update authorizations set code = ? where state = ?;", [code, state])

        token_request = requests.post(
            url=TOKEN_URL,
            headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': PROPER_USER_AGENT},
            data=f'redirect_uri={REDIRECT_URL}&code={code}&grant_type=authorization_code&code_verifier={code_verifier}'
                 f'&client_id={CLIENT_ID}')

        if token_request.status_code != 200:
            # Something went wrong
            print(f"error_id: {error_id}\n{token_request.text}")
            with sql_connection:
                sql_connection.execute("delete from authorizations where state = ?;", [state])
            sql_connection.close()
            raise falcon.HTTPBadRequest(description=f'Something went wrong, your error id is {error_id}')

        token_request = token_request.json()
        access_token = token_request["access_token"]
        refresh_token = token_request["refresh_token"]
        expires_in = token_request["expires_in"]
        timestamp_got_expires_in = int(time.time())

        with sql_connection:
            sql_connection.execute(
                "update authorizations set access_token = ?, refresh_token = ?, expires_in = ?, "
                "timestamp_got_expires_in = ? where state = ?",
                [access_token, refresh_token, expires_in, timestamp_got_expires_in, state])

        try:
            nickname = requests.get(
                url='https://companion.orerve.net/profile',
                headers={'Authorization': f'Bearer {access_token}',
                         'User-Agent': PROPER_USER_AGENT}).json()["commander"]["name"]
            try:
                sql_connection.execute("update authorizations set nickname = ? where state = ?;", [nickname, state])
                sql_connection.commit()
            except sqlite3.IntegrityError:
                already_saved_state = sql_connection.execute(
                    "select state from authorizations where nickname = ?", [nickname]).fetchone()[0]
                resp.text = f"We already have your token (CMDR {nickname}) in DB, your key: {already_saved_state}"
                with sql_connection:
                    sql_connection.execute("delete from authorizations where state = ?;", [state])
                sql_connection.close()
                return

        except Exception as e:
            resp.text = f"Something went wrong, your error id is {error_id}"
            print(f"error_id: {error_id}\n{e}")
            with sql_connection:
                sql_connection.execute("delete from authorizations where state = ?;", [state])
        else:  # all fine
            resp.text = f"All right, {nickname}, we have your tokens\nSave and keep this key: {state}"
        sql_connection.close()


class User:
    def on_get(self, req, resp, user):
        sql_connection = sqlite3.connect(database="companion-api.sqlite")
        if sql_connection.execute('select timestamp_got_expires_in, expires_in from authorizations where state = ?;',
                                  [user]).fetchone() is None:
            sql_connection.close()
            raise falcon.HTTPNotFound(description="Couldn't find you in DB")

        refresh_one_token(user)

        access_token, expires_timestamp, nickname = sql_connection.execute(
            'select access_token, timestamp_got_expires_in + expires_in, nickname from authorizations where state = ?',
            [user]).fetchone()

        import json
        resp.text = json.dumps({'access_token': access_token,
                                'expires_over': expires_timestamp - int(time.time()),
                                'expires_on': expires_timestamp,
                                'nickname': nickname})
        resp.content_type = falcon.MEDIA_JSON
        sql_connection.close()

    def on_delete(self, req, resp, user):
        sql_connection = sqlite3.connect(database="companion-api.sqlite")

        with sql_connection:
            sql_connection.execute('delete from authorizations where state = ?;', [user])
        sql_connection.close()


class Admin:
    def on_get(self, req, resp, _state):
        sql_connection = sqlite3.connect(database="companion-api.sqlite")
        try:
            if sql_connection.execute(
                    'select nickname from authorizations where state = ?;', [_state]).fetchone()[0] != 'Aleksey31':
                sql_connection.close()
                raise falcon.HTTPNotFound(description="You aren't an admin")

        except TypeError:
            raise falcon.HTTPNotFound(description="You aren't an admin")

        users_html = ""
        for user in sql_connection.execute(
                'select nickname, state from authorizations where nickname is not null;').fetchall():
            user_name = user[0]
            user_state = "/users/" + user[1]
            users_html = users_html + config.ADMIN_USER_TEMPLATE.format(link=user_state, desc=user_name) + "\n<br>\n"

        resp.content_type = falcon.MEDIA_HTML
        resp.text = config.ADMIN_USERS_TEMPLATE.format(users_html)
        sql_connection.close()


app = falcon.App()

# routing
app.add_route('/authorize', Authorize())
app.add_route('/fdev-redirect', FDEV_redirect())
app.add_route('/users/{user}', User())
app.add_route('/admin/{_state}', Admin())

waitress.serve(app, host='127.0.0.1', port=9000)
