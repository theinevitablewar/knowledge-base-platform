from enum import StrEnum


class Status(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"
    DELETED = "deleted"


class KBRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class Visibility(StrEnum):
    PRIVATE = "private"
    MEMBERS = "members"
    WORKSPACE = "workspace"
    TENANT = "tenant"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    DISABLED = "disabled"
    DELETING = "deleting"
    DELETED = "deleted"
