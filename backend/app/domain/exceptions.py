# backend/app/domain/exceptions.py
class DomainError(Exception):
    pass


class EntityNotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class IngestionError(DomainError):
    pass


class RetrievalError(DomainError):
    pass


class LLMError(DomainError):
    status_code: int = 503


class PromptNotFoundError(DomainError):
    """Raised when a prompt is not found."""
    pass


class PromptVariableError(DomainError):
    """Raised when a required prompt variable is missing."""
    pass


class TourSessionNotFound(DomainError):
    pass


class TourSessionExpired(DomainError):
    pass


class TourSessionTokenMismatch(DomainError):
    pass


class TourSessionStateConflict(DomainError):
    def __init__(self, expected_state_version: int, current_state_version: int):
        self.expected_state_version = expected_state_version
        self.current_state_version = current_state_version
        super().__init__(
            "Expected state_version "
            f"{expected_state_version}, current state_version is {current_state_version}"
        )
