"""Exception handling for tcc package

See https://docs.python.org/3/tutorial/errors.html#user-defined-exceptions
"""

import json

class TCCError(Exception):
    """Base error for package
    """
    pass

class HTTPCommunicationError(TCCError):
    """Wrapping exceptions from requests

    See https://julien.danjou.info/python-exceptions-guide under Wrapping Exceptions
    """
    def __init__(self, msg, orig_exc):
        super(HTTPCommunicationError, self).__init__('{}: {}'.format(msg, orig_exc))
        self.orig_exc = orig_exc

class ServerError(TCCError):
    """Raised when receive not 200 from server

    400: Probably something wrong with payload (e.g. option validation)
    401: Authentication
    Should not get anything else...
    """
    def __init__(self, request):
        code = request.status_code
        
        if code == 400:
            msg = "Server could not process request properly (code {})".format(code)
        elif code == 401:
            msg = "Server failed to authenticate user (code {})".format(code)
        elif code == 404:
            msg = "Server failed to find resource (code {})".format(code)
        else:
            msg = "Server returned unknown response (code {})".format(code)

        try:
            response = json.loads(request.text)

            message = response.get('message', None)
            errors = response.get('errors', None)

            if message is not None:
                msg += ': {}'.format(message)

            if isinstance(errors, dict):
                msg += '\n'
                for key in errors:
                    msg += "  {}: {}\n".format(key, str(errors[key]))
        except ValueError:
            msg = "Server did not provide valid response body (code {})".format(code)

        super(ServerError, self).__init__(msg)

        self.request = request

