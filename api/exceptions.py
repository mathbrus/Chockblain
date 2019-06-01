class ValidationError(Exception):
    def __init__(self, log):
        super().__init__()
        self.log = log
        print(log)


class HandlingError(Exception):
    def __init__(self, log):
        super().__init__()
        self.log = log
        print(log)


class FullnodeError(Exception):
    def __init__(self, log):
        super().__init__()
        self.log = log
        print(log)

