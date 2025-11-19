"""Profile tyro with many arguments to find bottlenecks."""
import cProfile

# Now manually import the config by reading and executing the file
import dataclasses
import io
import pstats
from pstats import SortKey

# Import tyro first
import tyro


@dataclasses.dataclass
class ExperimentConfig:
    """Copied from 0_many_args.py for profiling."""
    pass

# Read the actual config from the file
import importlib.util

spec = importlib.util.spec_from_file_location("many_args", "/Users/brentyi/tyro/benchmark/0_many_args.py")
many_args = importlib.util.module_from_spec(spec)
spec.loader.exec_module(many_args)
ExperimentConfig = many_args.ExperimentConfig


def run_benchmark():
    """Run tyro.cli with many arguments."""
    try:
        tyro.cli(ExperimentConfig, args=[])
    except SystemExit:
        pass


if __name__ == "__main__":
    # Profile the code
    profiler = cProfile.Profile()
    profiler.enable()
    run_benchmark()
    profiler.disable()

    # Print stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats(50)  # Top 50 functions by cumulative time
    print(s.getvalue())

    print("\n" + "="*80)
    print("TOP FUNCTIONS BY TIME (not cumulative)")
    print("="*80 + "\n")

    s2 = io.StringIO()
    ps2 = pstats.Stats(profiler, stream=s2).sort_stats(SortKey.TIME)
    ps2.print_stats(50)
    print(s2.getvalue())
