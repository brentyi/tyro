from dataclasses import dataclass


@dataclass(frozen=True, eq=False)
class _MutexGroupConfig:
    required: bool = False


def create_mutex_group(*, required: bool) -> _MutexGroupConfig:
    """Create a mutually exclusive group.

    # TODO: add example. note that `tyro.conf.DisallowNone` may be useful.
    """
    return _MutexGroupConfig(required=required)
