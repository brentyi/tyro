import dataclasses
import time

import tyro


@dataclasses.dataclass
class ExperimentConfig:
    arg000: int = 0
    arg001: int = 1
    arg002: int = 2
    arg003: int = 3
    arg004: int = 4
    arg005: int = 5
    arg006: int = 6
    arg007: int = 7
    arg008: int = 8
    arg009: int = 9


def main() -> None:
    start = time.perf_counter()
    tyro.cli(ExperimentConfig, args=[])
    print(f"Total time taken: {(time.perf_counter() - start) * 1000:.1f}ms")


if __name__ == "__main__":
    tyro.cli(main)
