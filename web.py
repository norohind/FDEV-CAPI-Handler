import falcon
import waitress
import json

import capi
from capi import capi_authorizer
import config
from EDMCLogging import get_main_logger

logger = get_main_logger()
logger.propagate = False


def check_secret(req: falcon.request.Request, resp: falcon.response.Response, resource, params) -> None:
    header_secret = req.headers.get('AUTH')  # for legacy reasons

    cookies_secret = req.get_cookie_values('key')

    if header_secret != config.access_key:
        if cookies_secret is None or cookies_secret[0] != config.access_key:
            raise falcon.HTTPForbidden


class AuthInit:
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response) -> None:
        resp.content_type = falcon.MEDIA_HTML
        resp.text = config.REDIRECT_HTML_TEMPLATE.format(link=capi_authorizer.auth_init())


class FDEVCallback:
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response) -> None:
        code = req.get_param('code')
        state = req.get_param('state')
        try:
            msg = capi_authorizer.fdev_callback(code, state)
            resp.content_type = falcon.MEDIA_JSON
            resp.text = json.dumps(msg)

        except KeyError as e:
            logger.warning(f'Exception on FDEVCallback, code: {code!r}, state: {state!r}', exc_info=e)
            raise falcon.HTTPNotFound(description=str(e))

        except Exception as e:
            logger.warning(f'Exception on FDEVCallback, code: {code!r}, state: {state!r}', exc_info=e)
            raise falcon.HTTPBadRequest(description=str(e))


class TokenByState:
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response, state: str) -> None:
        resp.content_type = falcon.MEDIA_JSON
        tokens = capi_authorizer.get_token_by_state(state)
        if tokens is None:
            raise falcon.HTTPNotFound(description='No such state found')

        resp.text = json.dumps(tokens)

    def on_delete(self, req: falcon.request.Request, resp: falcon.response.Response, state: str):
        tokens = capi_authorizer.get_token_by_state(state)
        if tokens is None:
            raise falcon.HTTPNotFound(description='No such state found')

        capi_authorizer.delete_by_state(state)


class TokenByNickname:
    @falcon.before(check_secret)
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response, nickname: str):
        resp.content_type = falcon.MEDIA_JSON
        state = capi_authorizer.model.get_state_by_nickname(nickname)
        if state is None:
            raise falcon.HTTPNotFound(description='No such nickname found')

        tokens = capi_authorizer.get_token_by_state(state)

        resp.text = json.dumps(tokens)

    @falcon.before(check_secret)
    def on_delete(self, req: falcon.request.Request, resp: falcon.response.Response, nickname: str):
        state = capi_authorizer.model.get_state_by_nickname(nickname)
        if state is None:
            raise falcon.HTTPNotFound(description='No such nickname found')

        capi_authorizer.delete_by_state(state)


class TokenByFID:
    NOT_FOUND_DESCRIPTION = 'No such FID was found'

    @falcon.before(check_secret)
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response, fid: str):
        resp.content_type = falcon.MEDIA_JSON

        state = capi_authorizer.model.get_state_by_fid(fid)
        if state is None:
            raise falcon.HTTPNotFound(description=self.NOT_FOUND_DESCRIPTION)

        tokens = capi.capi_authorizer.get_token_by_state(state)
        resp.text = json.dumps(tokens)

    @falcon.before(check_secret)
    def on_delete(self, req: falcon.request.Request, resp: falcon.response.Response, fid: str):
        state = capi_authorizer.model.get_state_by_fid(fid)
        if state is None:
            raise falcon.HTTPNotFound(description=self.NOT_FOUND_DESCRIPTION)

        capi_authorizer.delete_by_state(state)


class CleanOrphanRecords:
    def on_post(self, req: falcon.request.Request, resp: falcon.response.Response):
        capi_authorizer.cleanup_orphans()


class ListTokens:
    @falcon.before(check_secret)
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response):
        resp.content_type = falcon.MEDIA_JSON
        resp.text = json.dumps(capi_authorizer.list_all_valid_users())


class RandomToken:
    # for legacy reasons
    @falcon.before(check_secret)
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response):
        resp.content_type = falcon.MEDIA_JSON
        import random
        list_users = capi_authorizer.list_all_valid_users()

        if len(list_users) == 0:
            raise falcon.HTTPNotFound(description='No users in DB')

        random_user = random.choice(list_users)

        resp.text = json.dumps(capi_authorizer.get_token_by_state(random_user['state']))


application = falcon.App()
application.add_route('/authorize', AuthInit())
application.add_route('/fdev-redirect', FDEVCallback())
application.add_route('/users/{state}', TokenByState())  # for legacy reasons
application.add_route('/random_token', RandomToken())  # for legacy reasons, subject to decommissioning
application.add_route('/users/by-state/{state}', TokenByState())
application.add_route('/users/by-nickname/{nickname}', TokenByNickname())
application.add_route('/users/by-fid/{fid}', TokenByFID())
application.add_route('/users', ListTokens())
application.add_route('/tools/clean-orphan-records', CleanOrphanRecords())

if __name__ == '__main__':
    waitress.serve(application, host='127.0.0.1', port=9000)
