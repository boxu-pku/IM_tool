"""Hugoniot data validation tools."""

__all__ = ['validate_file', 'ValidationResult']


def __getattr__(name):
    # Allow the validator to run as a module without preloading it during package import.
    if name in __all__:
        from . import validate_hugoniot

        return getattr(validate_hugoniot, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
