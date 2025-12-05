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
    arg010: int = 10
    arg011: int = 11
    arg012: int = 12
    arg013: int = 13
    arg014: int = 14
    arg015: int = 15
    arg016: int = 16
    arg017: int = 17
    arg018: int = 18
    arg019: int = 19
    arg020: int = 20
    arg021: int = 21
    arg022: int = 22
    arg023: int = 23
    arg024: int = 24
    arg025: int = 25
    arg026: int = 26
    arg027: int = 27
    arg028: int = 28
    arg029: int = 29
    arg030: int = 30
    arg031: int = 31
    arg032: int = 32
    arg033: int = 33
    arg034: int = 34
    arg035: int = 35
    arg036: int = 36
    arg037: int = 37
    arg038: int = 38
    arg039: int = 39
    arg040: int = 40
    arg041: int = 41
    arg042: int = 42
    arg043: int = 43
    arg044: int = 44
    arg045: int = 45
    arg046: int = 46
    arg047: int = 47
    arg048: int = 48
    arg049: int = 49
    arg050: int = 50
    arg051: int = 51
    arg052: int = 52
    arg053: int = 53
    arg054: int = 54
    arg055: int = 55
    arg056: int = 56
    arg057: int = 57
    arg058: int = 58
    arg059: int = 59
    arg060: int = 60
    arg061: int = 61
    arg062: int = 62
    arg063: int = 63
    arg064: int = 64
    arg065: int = 65
    arg066: int = 66
    arg067: int = 67
    arg068: int = 68
    arg069: int = 69
    arg070: int = 70
    arg071: int = 71
    arg072: int = 72
    arg073: int = 73
    arg074: int = 74
    arg075: int = 75
    arg076: int = 76
    arg077: int = 77
    arg078: int = 78
    arg079: int = 79
    arg080: int = 80
    arg081: int = 81
    arg082: int = 82
    arg083: int = 83
    arg084: int = 84
    arg085: int = 85
    arg086: int = 86
    arg087: int = 87
    arg088: int = 88
    arg089: int = 89
    arg090: int = 90
    arg091: int = 91
    arg092: int = 92
    arg093: int = 93
    arg094: int = 94
    arg095: int = 95
    arg096: int = 96
    arg097: int = 97
    arg098: int = 98
    arg099: int = 99


def main() -> None:
    start = time.perf_counter()
    tyro.cli(ExperimentConfig, args=[])
    print(f"Total time taken: {(time.perf_counter() - start) * 1000:.1f}ms")


if __name__ == "__main__":
    tyro.cli(main)
