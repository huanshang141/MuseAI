"""Shared response models used by multiple API routers."""

from pydantic import BaseModel


class BaseDeleteResponse(BaseModel):
    """Common payload shape for delete operations."""

    status: str


class SessionDeleteResponse(BaseDeleteResponse):
    session_id: str


class DocumentDeleteResponse(BaseDeleteResponse):
    document_id: str


class ExhibitDeleteResponse(BaseDeleteResponse):
    exhibit_id: str
