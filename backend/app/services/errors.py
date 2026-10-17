class NotFoundError(Exception):
    """The entity does not exist or the caller cannot see it (indistinguishable on purpose)."""


class ForbiddenError(Exception):
    """The caller can see the entity (shared with them) but only its owner may do this."""


class ConflictError(Exception):
    """The request is valid but clashes with the current state (e.g. a run is already in progress)."""
