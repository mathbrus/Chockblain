class ValidationError(Exception):
    def __init__(self, log):
        super().__init__()
        self.log = log
        print(log)


class APIError(Exception):
    def __init__(self, log):
        super().__init__()
        self.log = log
        print(log)


class FullnodeError(Exception):
    def __init__(self, log):
        super().__init__()
        self.log = log
        print(log)

