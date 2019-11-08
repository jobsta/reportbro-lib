

class ReportBroError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return 'ReportBroError: ' + ', '.join(
            ['{key}={value}'.format(key=key, value=self.error.get(key)) for key in self.error])


class Error(dict):
    def __init__(self, msg_key, object_id=None, field=None, info=None, context=None):
        dict.__init__(self, msg_key=msg_key, object_id=object_id, field=field, info=info, context=context)
