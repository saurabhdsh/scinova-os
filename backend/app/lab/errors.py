"""Structured lab errors. Numeric science never travels through these messages alone."""


class LabError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "lab_error", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}

    def as_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "details": self.details}
