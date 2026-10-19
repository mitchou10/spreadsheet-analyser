class NotFoundError(Exception):
    """The entity does not exist or the caller cannot see it (indistinguishable on purpose)."""


class ForbiddenError(Exception):
    """The caller can see the entity (shared with them) but only its owner may do this."""


class ConflictError(Exception):
    """The request is valid but clashes with the current state (e.g. a run is already in progress)."""


class InvalidRequestError(Exception):
    """The request is well formed but makes no sense for this entity (e.g. feedback on a user message)."""


class UnknownFilesError(NotFoundError):
    """Files named by their hash are not (or no longer) available as already analysed."""

    def __init__(self, hashes: list[str]) -> None:
        super().__init__(f"{len(hashes)} file(s) not available as already analysed")
        self.hashes = hashes
