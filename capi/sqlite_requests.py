schema = """create table if not exists authorizations (
    code_verifier text , 
    state text, 
    timestamp_init datetime default current_timestamp , 
    code text, 
    access_token text, 
    refresh_token text, 
    expires_in text, 
    timestamp_got_expires_in text, 
    nickname text unique,
    refresh_tries int default 0
);"""

insert_auth_init = """insert into authorizations 
    (code_verifier, state) 
    values 
    (:code_verifier, :state);"""

select_all_by_state = """select * from authorizations where state = :state;"""

set_code_state = """update authorizations set code = :code where state = :state;"""

delete_by_state = """delete from authorizations where state = :state;"""

set_tokens_by_state = """update authorizations 
set 
    access_token = :access_token, 
    refresh_token = :refresh_token, 
    expires_in = :expires_in, 
    timestamp_got_expires_in = :timestamp_got_expires_in, 
    refresh_tries = 0
where state = :state;"""

set_nickname_by_state = """update authorizations set nickname = :nickname where state = :state;"""

get_state_by_nickname = """select state from authorizations where nickname = :nickname;"""

update_state_by_state = """update authorizations set state = :new_state where state = :state;"""

refresh_times_increment = """update authorizations set refresh_tries = refresh_tries + 1 where state = :state;"""

get_token_for_user = """select 
    access_token, 
    timestamp_got_expires_in + expires_in as expires_on, 
    nickname 
from authorizations where state = :state;"""

select_nickname_state_all = """select nickname, state from authorizations where nickname is not null;"""