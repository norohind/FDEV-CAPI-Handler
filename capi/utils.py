import hashlib
import base64
import requests
import config


def get_tokens_request(code, code_verifier) -> requests.Response:
    """
    Performs initial requesting access and refresh tokens

    :param code:
    :param code_verifier:
    :return:
    """
    token_request: requests.Response = requests.post(
        url=config.TOKEN_URL,
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': config.PROPER_USER_AGENT
        },
        data=f'redirect_uri={config.REDIRECT_URL}&'
             f'code={code}&'
             f'grant_type=authorization_code&'
             f'code_verifier={code_verifier}&'
             f'client_id={config.CLIENT_ID}')

    return token_request


def get_nickname(access_token: str) -> str:
    return requests.get(
        url='https://companion.orerve.net/profile',
        headers={'Authorization': f'Bearer {access_token}',
                 'User-Agent': config.PROPER_USER_AGENT}).json()["commander"]["name"]


def refresh_request(refresh_token: str) -> requests.Response:
    return requests.post(
        url=config.TOKEN_URL,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data=f'grant_type=refresh_token&client_id={config.CLIENT_ID}&refresh_token={refresh_token}')


def generate_challenge(_verifier: bytes) -> str:
    """
    It takes code verifier and return code challenge
    :param _verifier:
    :return:
    """
    return base64.urlsafe_b64encode(hashlib.sha256(_verifier).digest())[:-1].decode('utf-8')
