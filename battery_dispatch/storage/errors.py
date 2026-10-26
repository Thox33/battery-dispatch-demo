"""Errors raised by the storage layer."""


class StorageUnavailableError(Exception):
    """The database cannot be reached, for example because it is stopped or unresolvable."""
