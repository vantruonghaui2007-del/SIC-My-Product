"""External music providers. Generation errors never include upstream secrets."""


class MusicProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
