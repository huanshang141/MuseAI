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
    pass
