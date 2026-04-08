# backend/app/domain/value_objects.py
from dataclasses import dataclass


@dataclass(frozen=True)
class UserId:
    value: str


@dataclass(frozen=True)
class SessionId:
    value: str


@dataclass(frozen=True)
class DocumentId:
    value: str


@dataclass(frozen=True)
class JobId:
    value: str


@dataclass(frozen=True)
class ChunkId:
    value: str


@dataclass(frozen=True)
class TraceId:
    value: str


@dataclass(frozen=True)
class ExhibitId:
    value: str


@dataclass(frozen=True)
class TourPathId:
    value: str


@dataclass(frozen=True)
class ProfileId:
    value: str


@dataclass(frozen=True)
class PromptId:
    value: str


@dataclass(frozen=True)
class Location:
    x: float
    y: float
    floor: int = 1
