from dataclasses import dataclass


@dataclass
class Finding:
    path: str
    line: int
    col: int
    level: str
    rule: str
    message: str

    def text(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.level}: {self.message} [{self.rule}]"

    def github(self) -> str:
        def escape(value: str, properties: bool = False) -> str:
            value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            if properties:
                value = value.replace(":", "%3A").replace(",", "%2C")
            return value

        location = f"file={escape(self.path, True)},line={self.line},col={self.col},title={escape(self.rule, True)}"
        return f"::{self.level} {location}::{escape(self.message)}"


class Report:
    def __init__(self, path: str):
        self.path = path
        self.findings: list[Finding] = []

    def error(self, line: int, rule: str, message: str, col: int = 1) -> None:
        self.findings.append(Finding(self.path, line, col, "error", rule, message))

    def warning(self, line: int, rule: str, message: str, col: int = 1) -> None:
        self.findings.append(Finding(self.path, line, col, "warning", rule, message))
