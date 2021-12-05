import falcon
import waitress
import json

from capi import capi_authorizer
import config


class AuthInit:
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response) -> None:
        resp.content_type = falcon.MEDIA_HTML
        resp.text = config.REDIRECT_HTML_TEMPLATE.format(link=capi_authorizer.auth_init())


class FDEVCallback:
    def on_get(self, req: falcon.request.Request, resp: falcon.response.Response) -> None:
        code = req.get_param('code')
        state = req.get_param('state')
        msg = capi_authorizer.fdev_callback(code, state)
        resp.content_type = falcon.MEDIA_JSON
        resp.text = json.dumps(msg)


application = falcon.App()
application.add_route('/authorize', AuthInit())
application.add_route('/fdev-redirect', FDEVCallback())

if __name__ == '__main__':
    waitress.serve(application, host='127.0.0.1', port=9000)