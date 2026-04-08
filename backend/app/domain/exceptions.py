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
