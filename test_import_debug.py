#!/usr/bin/env python3
import sys

sys.path.insert(0, '/home/brent/tyro/src')

print("About to import type_to_tyro_type...")
from tyro._tyro_type import type_to_tyro_type

print("Imported successfully")

# Check the function's source
import inspect

source = inspect.getsource(type_to_tyro_type)
print("\nFunction source (first 1000 chars):")
print(source[:1000])

print("\n---\nNow testing the function:\n")

from typing_extensions import Annotated


class Animal:
    pass

annotated_animal = Annotated[Animal, 'some_metadata']
print(f"Input: {annotated_animal}")
result = type_to_tyro_type(annotated_animal)
print(f"Result: {result}")
