import requests

from . import model
from . import utils
from . import exceptions

import base64
import os
import time
from typing import Union

import config
from EDMCLogging import get_main_logger

logger = get_main_logger()


class CAPIAuthorizer:
    def __init__(self, _model: model.Model):
        self.model: model.Model = _model

    def auth_init(self) -> str:
        """
        Generates initial url for fdev auth

        :return:
        """

        code_verifier = base64.urlsafe_b64encode(os.urandom(32))
        code_challenge = utils.generate_challenge(code_verifier)
        state_string = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")

        self.model.auth_init(code_verifier.decode('utf-8'), state_string)

        redirect_user_to_fdev = f"{config.AUTH_URL}?" \
                                f"audience=all&" \
                                f"scope=capi&" \
                                f"response_type=code&" \
                                f"client_id={config.CLIENT_ID}&" \
                                f"code_challenge={code_challenge}&" \
                                f"code_challenge_method=S256&" \
                                f"state={state_string}&" \
                                f"redirect_uri={config.REDIRECT_URL}"

        return redirect_user_to_fdev

    def fdev_callback(self, code: str, state: str) -> dict[str, str]:
        if type(code) is not str or type(state) != str:
            raise TypeError('code and state must be strings')

        code_verifier = self.model.get_verifier(state)

        self.model.set_code(code, state)

        token_request = utils.get_tokens_request(code, code_verifier)

        try:
            token_request.raise_for_status()

        except Exception as e:
            logger.exception(
                f'token_request failed. Status: {token_request.status_code!r}, text: {token_request.text!r}',
                exc_info=e
            )

            # self.model.delete_row(state)

            raise e

        tokens = token_request.json()

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_in = tokens["expires_in"]
        timestamp_got_expires_in = int(time.time())

        self.model.set_tokens(access_token, refresh_token, expires_in, timestamp_got_expires_in, state)

        nickname = utils.get_nickname(access_token)
        self.model.set_nickname(nickname, state)
        if nickname is None:
            logger.warning(f"Couldn't get or set nickname for state: {state!r}")  # msg inform: no nickname

        fid = utils.get_fid(access_token)
        if fid is None:
            logger.error(f"Couldn't get FID for state: {state!r}")
            raise exceptions.NoFID(f'No FID for {state!r}')

        msg = {'status': 'ok', 'description': '', 'state': ''}

        if not self.model.set_fid(fid, state):
            msg['description'] = 'Tokens updated'

        else:
            msg['description'] = 'Tokens saved'

        msg['state'] = self.model.get_state_by_fid(fid)

        return msg

    def get_token_by_state(self, state: str) -> Union[dict, None]:
        try:
            self.refresh_by_state(state)

        except exceptions.CAPIException:
            return None

        row = self.model.get_token_for_user(state)

        if row is None:
            return None

        row['expires_over'] = int(row['expires_on']) - int(time.time())

        return row

    def refresh_by_state(self, state: str, force_refresh=False, failure_tolerance=True) -> dict:
        """

        :param state:
        :param force_refresh: if we should update token when its time hasn't come
        :param failure_tolerance: if we shouldn't remove row in case of update's failure
        :return:
        """

        msg = {'status': '', 'description': '', 'state': ''}
        row = self.model.get_row(state)

        if row is None:
            # No such state in DB
            msg['status'] = 'error'
            msg['description'] = 'No such state in DB'
            raise exceptions.RefreshFail(msg['description'], msg['status'], state)

        msg['state'] = state

        if int(time.time()) < int(row['timestamp_got_expires_in']) + int(row['expires_in']) - 400 and not force_refresh:
            # current time < when we got token + token lifetime - 400, 400 is need just to refresh token on 400 secs
            # earlier than lifetime stated by FDEV, for safe
            msg['status'] = 'ok'
            msg['description'] = "Didn't refresh since it isn't required"

            return msg  # token isn't expired and we don't force updating

        try:
            refresh_request = utils.refresh_request(row['refresh_token'])
            if refresh_request.status_code == 418:  # Server's maintenance
                logger.warning(f'FDEV maintenance 418, text: {refresh_request.text!r}')
                msg['status'] = 'error'
                msg['description'] = 'FDEV on maintenance'
                raise exceptions.RefreshFail(msg['message'], msg['status'], state)

            refresh_request.raise_for_status()

            tokens = refresh_request.json()
            self.model.set_tokens(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                expires_in=tokens["expires_in"],
                timestamp_got_expires_in=int(time.time()),
                state=state
            )
            msg['status'] = 'ok'
            msg['description'] = 'Token were successfully updated'
            return msg

        except requests.ConnectionError as e:
            logger.warning(f'Connection problem on refresh for {state!r}', exc_info=e)
            msg['status'] = 'error'
            msg['description'] = 'Connection Error'
            raise exceptions.RefreshFail(msg['description'], msg['status'], state)

        except Exception as e:
            # probably here something don't work
            text = ''
            try:
                text = refresh_request.text

            except Exception as e1:
                text = f"can't get text because {e1}"

            logger.warning(
                f'Fail on refreshing token for {state!r}, row:{row!r}, text: {text}', exc_info=e)
            msg['status'] = 'error'

            self.model.increment_refresh_tries(state)

            if not failure_tolerance:
                if row['refresh_tries'] >= 5:  # hardcoded limit
                    msg['description'] = "Refresh failed. You were removed from DB due to refresh rate limitings"
                    self.model.delete_row(state)
                    raise exceptions.RefreshFail(msg['description'], msg['status'], state)

            msg['description'] = "Refresh failed. Try later"
            raise exceptions.RefreshFail(msg['description'], msg['status'], state)

    def delete_by_state(self, state: str) -> None:
        self.model.delete_row(state)

    def list_all_valid_users(self) -> list[dict]:
        return self.model.list_all_valid_records()

    def cleanup_orphans(self) -> None:
        self.model.cleanup_orphans_records()

    def list_all_records(self) -> list[dict]:
        return self.model.list_all_records()


capi_authorizer = CAPIAuthorizer(model.Model())
