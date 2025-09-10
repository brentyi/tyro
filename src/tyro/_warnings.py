"""Custom warning category for tyro."""


class TyroWarning(UserWarning):
    """Warning category for tyro-specific warnings.

    This can be used to filter tyro warnings:
    >>> import warnings
    >>> warnings.filterwarnings("ignore", category=TyroWarning)
    """

    pass
