class ValidationError(Exception):
    def __init__(self, log):
        super().__init__()
        self.log = log


class HandlingError(Exception):
    def __init__(self, log):
        super().__init__()
        self.log = log
