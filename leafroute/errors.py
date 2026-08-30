class LeafRouteError(Exception):
    """Base LeafRoute exception."""


class UnsupportedDocumentError(LeafRouteError):
    """Raised when no parser exists for a document type."""


class ArtifactVersionError(LeafRouteError):
    """Raised when an artifact version is not supported."""


class OfflineViolationError(LeafRouteError):
    """Raised when a network provider is used in offline mode."""
