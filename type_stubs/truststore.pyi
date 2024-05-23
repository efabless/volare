import ssl

class SSLContext(ssl.SSLContext):
    def __init__(self, protocol: int) -> None: ...
