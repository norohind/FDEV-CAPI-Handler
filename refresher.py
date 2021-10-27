import sqlite3
from config import CLIENT_ID, TOKEN_URL
import requests
import time
from hashlib import sha256
from os import urandom

"""
1. For every expired access token in DB:
    Utilise refresh token and write new access_token, refresh_token, expires_in to DB

"""


def refresh_one_token(_state: str, _force: bool = False):
    error_id = sha256(urandom(32)).hexdigest()
    sql_connection = sqlite3.connect(database="companion-api.sqlite")
    try:
        tokens_sql_request = sql_connection.execute(
            'select refresh_token, timestamp_got_expires_in, expires_in from authorizations where state = ?;',
            [_state]).fetchone()

        if int(time.time()) < int(tokens_sql_request[1]) + int(tokens_sql_request[2]) and not _force:
            return  # token isn't expired and _force is not True

        refresh_token = tokens_sql_request[0]
        refresh_request = requests.post(
            url=TOKEN_URL,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data=f'grant_type=refresh_token&client_id={CLIENT_ID}&refresh_token={refresh_token}')

        if refresh_request.status_code == 418:  # Server's maintenance
            print(f"Error id {error_id}, got 418 status code, {refresh_request.text}")
            sql_connection.close()
            return

        try:
            refresh_request_json = refresh_request.json()

        except Exception as e2:
            print(f'Error id: {error_id}\n{refresh_request.text, refresh_request.status_code}, {e2}')
            sql_connection.close()
            return

        new_access_token = refresh_request_json["access_token"]
        new_refresh_token = refresh_request_json["refresh_token"]
        new_expires_in = refresh_request_json["expires_in"]

        sql_connection.execute("update authorizations set access_token = ?, refresh_token = ?, expires_in = ?, "
                               "timestamp_got_expires_in = ? where state = ?;",
                               [new_access_token, new_refresh_token, new_expires_in, int(time.time()), _state])
        sql_connection.commit()

    except Exception as e:
        print(f'Error id: {error_id}\n{e}\nRequest result: {refresh_request.text}, code '
              f'{refresh_request.status_code}')
        sql_connection.execute("delete from authorizations where state = ?;", [_state])
        sql_connection.commit()
        sql_connection.close()
        raise e
    sql_connection.close()


def refresh_all_suitable_tokens():
    sql_connection = sqlite3.connect(database="companion-api.sqlite")
    suitable_tokens = sql_connection.execute("select state from authorizations;")

    for state in suitable_tokens.fetchall():
        state = state[0]
        refresh_one_token(state)
    sql_connection.close()
