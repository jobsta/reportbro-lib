

class ReportBroError(Exception):
    pass


class Error(dict):
    def __init__(self, msg_key, object_id=None, field=None, info=None):
        dict.__init__(self, msg_key=msg_key, object_id=object_id, field=field, info=info)
