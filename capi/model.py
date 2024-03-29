import sqlite3
from typing import Union

from . import sqlite_requests
from EDMCLogging import get_main_logger

logger = get_main_logger()


class Model:
    def __init__(self, db_location: str):
        self.db: sqlite3.Connection = sqlite3.connect(db_location, check_same_thread=False)
        self.db.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        with self.db:
            self.db.execute(sqlite_requests.schema)

    def auth_init(self, verifier: str, state: str) -> None:
        with self.db:
            self.db.execute(
                sqlite_requests.insert_auth_init,
                {
                    'code_verifier': verifier,
                    'state': state
                })

    def get_verifier(self, state: str) -> str:
        code_verifier_req = self.db.execute(sqlite_requests.select_all_by_state, {'state': state}).fetchone()

        if code_verifier_req is None:
            # Somebody got here not by frontier redirect
            raise KeyError('No state in DB found')

        code_verifier: str = code_verifier_req['code_verifier']

        return code_verifier

    def set_code(self, code: str, state: str) -> None:
        with self.db:
            self.db.execute(sqlite_requests.set_code_state, {'code': code, 'state': state})

    def delete_row(self, state: str) -> None:
        with self.db:
            self.db.execute(sqlite_requests.delete_by_state, {'state': state})

    def set_tokens(self, access_token: str, refresh_token: str, expires_in: int, timestamp_got_expires_in: int,
                   state: str) -> None:

        with self.db:
            self.db.execute(
                sqlite_requests.set_tokens_by_state,
                {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'expires_in': expires_in,
                    'timestamp_got_expires_in': timestamp_got_expires_in,
                    'state': state
                 })

    def set_fid(self, fid: str, state: str) -> bool:
        """
        Return True if inserted successfully, False if catch sqlite3.IntegrityError

        :param fid:
        :param state:
        :return:
        """

        try:
            with self.db:
                self.db.execute(
                    sqlite_requests.set_fid_by_state,
                    {'fid': fid, 'state': state}
                )
            return True

        except sqlite3.IntegrityError:
            """
            let's migrate new received data to old state
            1. Get old state by fid
            2. Remove row with old state
            3. Set old state where new state
            """
            state_to_set: str = self.get_state_by_fid(fid)
            self.delete_row(state_to_set)
            self.set_new_state(state_to_set, state)
            with self.db:
                self.db.execute(
                    sqlite_requests.set_fid_by_state,
                    {'fid': fid, 'state': state_to_set}
                )
            return False

    def set_nickname(self, nickname: Union[str, None], state: str) -> None:
        with self.db:
            self.db.execute(
                sqlite_requests.set_nickname_by_state,
                {'nickname': nickname, 'state': state}
            )

    def get_state_by_nickname(self, nickname: str) -> Union[None, str]:
        with self.db:
            nickname_f1 = self.db.execute(sqlite_requests.get_state_by_nickname, {'nickname': nickname}).fetchone()

            if nickname_f1 is None:
                return None

            return nickname_f1['state']

    def get_state_by_fid(self, fid: str) -> Union[None, str]:
        with self.db:
            fid_req_dict = self.db.execute(sqlite_requests.get_state_by_fid, {'fid': fid}).fetchone()

            if fid_req_dict is None:
                return None

            return fid_req_dict['state']

    def set_new_state(self, new_state: str, old_state: str) -> None:
        with self.db:
            self.db.execute(sqlite_requests.update_state_by_state, {'new_state': new_state, 'state': old_state})

    def get_row(self, state: str) -> dict:
        return self.db.execute(sqlite_requests.select_all_by_state, {'state': state}).fetchone()

    def increment_refresh_tries(self, state: str) -> None:
        with self.db:
            self.db.execute(sqlite_requests.refresh_times_increment, {'state': state})

    def get_token_for_user(self, state: str) -> dict:
        sql_params = {'state': state}
        token = self.db.execute(sqlite_requests.get_token_for_user, sql_params).fetchone()
        with self.db:
            self.db.execute(sqlite_requests.increment_usages, sql_params)

        return token

    def list_all_valid_records(self) -> list:
        return self.db.execute(sqlite_requests.select_nickname_state_all).fetchall()

    def cleanup_orphans_records(self) -> None:
        with self.db:
            self.db.execute(sqlite_requests.del_orphans)

    def list_all_records(self) -> list[dict]:
        return self.db.execute(sqlite_requests.select_all).fetchall()
