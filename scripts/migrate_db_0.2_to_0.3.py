import sqlite3
import capi

db = sqlite3.connect('companion-api.sqlite')


backup_table_request = "ALTER TABLE authorizations RENAME TO authorizations_bak;"

restore_table_request = """
INSERT INTO authorizations (
    code_verifier, 
    state, 
    timestamp_init, 
    code, 
    access_token, 
    refresh_token, 
    expires_in, 
    timestamp_got_expires_in, 
    nickname, 
    refresh_tries,
    usages
)
SELECT 
    code_verifier, 
    state, 
    timestamp_init, 
    code, 
    access_token, 
    refresh_token, 
    expires_in, 
    timestamp_got_expires_in, 
    nickname, 
    refresh_tries,
    usages 
FROM authorizations_bak;
"""

drop_old_table_request = "drop table authorizations_bak;"

with db:
    db.execute(backup_table_request)
    db.execute(capi.sqlite_requests.schema)
    db.execute(restore_table_request)
    db.execute(drop_old_table_request)

db.close()  # schema migration ended, begin inserting fids

all_records = capi.capi_authorizer.list_all_records()
for record in all_records:
    if record['fid'] is None and record['nickname'] is not None:
        fid = capi.utils.get_fid(record['access_token'])
        capi.capi_authorizer.model.set_fid(fid, record['state'])
