from typing import Literal

ToolErrorType = Literal[
    "timeout",
    "validation_error",
    "not_found",
    "permission_denied",
    "external_failure",
    "empty_result",
]

RECOVERABLE_ERRORS: set[str] = {"empty_result", "timeout"}
UNRECOVERABLE_ERRORS: set[str] = {"validation_error", "not_found", "permission_denied", "external_failure"}


def is_recoverable(error_type: ToolErrorType) -> bool:
    return error_type in RECOVERABLE_ERRORS
