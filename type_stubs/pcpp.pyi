from io import StringIO
from typing import Optional

class Preprocessor(object):
    line_directive: Optional[str] = "#line"

    def __init__(self) -> None: ...
    def parse(self, input, source: Optional[str] = None, ignore: dict = {}): ...
    def write(self, io: StringIO): ...
