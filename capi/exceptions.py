class CAPIException(Exception):
    pass


class RefreshFail(CAPIException):
    def __init__(self, message: str, status: str, state: str):
        self.message = message
        self.status = status
        self.state = state
        super().__init__(str(self.message) + ' for ' + str(self.state))


class NoFID(Exception):
    pass
