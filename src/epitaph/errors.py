from __future__ import annotations


class EpitaphError(Exception):
    """Error de dominio con causa y siguiente paso."""

    exit_code = 1

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def render(self) -> str:
        text = f"✖ {self.message}"
        if self.hint:
            text += f"\n  Acción: {self.hint}"
        return text


class ConfigError(EpitaphError):
    exit_code = 1


class AnalysisError(EpitaphError):
    exit_code = 2


class LLMUnavailable(EpitaphError):
    exit_code = 3


class InvalidModelOutput(EpitaphError):
    exit_code = 4


class PermissionDenied(EpitaphError):
    exit_code = 5


class DirtyWorkTree(EpitaphError):
    exit_code = 6


class RunTimeout(EpitaphError):
    exit_code = 7
