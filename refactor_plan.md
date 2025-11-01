# TyroType Refactoring Plan

## Goals

### Primary Goal: Eliminate Expensive Type Reconstruction

Current code frequently creates new type objects at runtime:

```python
# Creating Union types dynamically
return Union[options + (type(default_instance),)]

# Creating Annotated types dynamically
return Annotated[(potential_subclass,) + get_args(typ)[1:]]

# Using .copy_with() which creates new type objects
return typ.copy_with(new_args)

# Reconstructing Tuples
return Tuple[default_types]
```

**These operations are expensive because:**

- Allocating new type objects has overhead
- Calling into `typing` module machinery
- Python's type system bookkeeping

### Secondary Goal: Make Annotated Handling Explicit

Current code has unclear handling where any type might be:

- `int`
- `Annotated[int, marker]`
- `Annotated[Annotated[int, marker1], marker2]`

This leads to bugs where we:

- Forget to unwrap before checking
- Forget to preserve annotations when transforming
- Have inconsistent patterns

### Solution: TyroType Everywhere

```python
@dataclasses.dataclass(frozen=True)
class TyroType:
    type_origin: Any   # The base type (int, list, Union, etc.). We use `Any` because `Union` is not a "type".
    args: tuple[Union[TyroType, Any], ...]  # Can contain TyroTypes or literals
    annotations: tuple[Any, ...]
```

**Benefits:**

- No reconstruction: `TyroType(Union, new_args, annotations)` instead of creating `Union[...]`
- Explicit runtime annotations: Always in `.annotations`. We never need to worry about unwrapping annotated types, which we currently do frequently.
- Cheap transformations: Just create new TyroType with different args

## Previous Attempt (October 2024)

### A Previous, Failed Attempt

1. Added TyroType dataclass with `type_origin`, `args`, `annotations`
2. Changed internal representations throughout codebase
3. Updated ~20 files to use TyroType
4. Fixed bugs as they appeared

### Results

- ❌ **Performance: 2x SLOWER** (0.20s vs 0.11s baseline)
- ⚠️ **Tests: 103 failures** (down from 115, but still many)
- ❌ **Bugs introduced:**
  - `narrow_subtypes()` was stripping type args from `Tuple[int, ...]`
  - `narrow_collection_types()` was incorrectly detecting `Any`
  - TypeVar annotation preservation broken
  - DummyWrapper losing type arguments

### Why It Failed

**1. Made performance WORSE instead of better**

- Unknown why - we eliminated reconstruction but got slower
- Possible causes:
  - TyroType creation overhead too high?
  - Still reconstructing somewhere we didn't notice?
  - Caching broken or ineffective?
  - Comparison/hashing slower?

**2. Introduced subtle bugs**

- Functions like `narrow_subtypes()` were designed for raw types
- Retrofitting onto TyroType changed behavior in unexpected ways
- Hard to reason about correctness

**3. No validation cadence**

- Changed everything, then debugged
- Never had a working intermediate state
- Couldn't isolate what changes caused what problems

## Key Insight: Why This Is Hard

**The codebase is deeply entangled:**

```
_resolver.py (unwrap_annotated, narrow_subtypes, etc.)
    ↓ used by
constructors/_struct_spec.py (StructTypeInfo, rules)
    ↓ used by
_fields.py (FieldDefinition, field_list_from_type_or_callable)
    ↓ used by
_arguments.py (ArgumentDefinition)
    ↓ used by
_parsers.py
```

**Cannot change one module independently:**

- If `unwrap_annotated()` returns TyroType, all 20+ callers break
- If `FieldDefinition.type` is TyroType, all code using it breaks
- Must change everything at once

**Converting TyroType <-> raw type defeats the purpose:**

- Conversion requires reconstruction
- Would lose all performance benefits
- So we need TyroType everywhere, not just in hot paths

## Proposed Path Forward

We will try again, but with a more cautious, measured approach.

### Phase 0: Measure performance

First, verify that `pyright` passes.

You can do this by running:

```
python benchmark/benchmark_wide_loop.py
```

This will directly print times. At the start, we should get:

```
Total time taken: 0.22 seconds
Total time taken: 0.21 seconds
Total time taken: 0.21 seconds
Total time taken: 0.21 seconds
Total time taken: 0.21 seconds
```

### Phase 1: Add TyroType Infrastructure (If proceeding)

**Add without changing existing code:**

```python
@dataclasses.dataclass(frozen=True)
class TyroType:
    type_origin: Any
    args: tuple[Union[TyroType, Any], ...]  # Can contain TyroTypes or literals
    annotations: tuple[Any, ...]

def type_to_tyro_type(typ: TypeForm) -> TyroType: ...
def reconstruct_type_from_tyro_type(tyro: TyroType) -> TypeForm: ...
```

**Validation:**

- All tests pass (no behavior change)
- Performance unchanged

**Commit:** "Add TyroType infrastructure"

### Phase 2: Change All Signatures Atomically

**Single commit changing:**

- `FieldDefinition.type: TyroType`
- `FieldDefinition.type_stripped: TyroType`
- `StructFieldSpec.type: TyroType`
- `StructTypeInfo`: store as TyroType components
- All `_resolver.py` functions: take/return TyroType
- `ArgumentDefinition.field: FieldDefinition`

**Expected result:** Tests and Pyright fail (type errors everywhere)

**Commit:** "Change all type signatures to TyroType (breaks tests)"

### Phase 3: Fix File by File

**Order (dependency order):**

1. `_resolver.py` - Core type operations
2. `constructors/_primitive_spec.py` - Primitive type handling
3. `constructors/_struct_spec.py` - Struct type handling
4. `_fields.py` - Field definitions
5. `_arguments.py` - Argument definitions
6. `_parsers.py` - Parser logic
7. `_calling.py` - Call instantiation
8. Other files as needed

**For each file:**

- Fix type errors from Pyright
- Run `pytest --backend=tyro ./tests/test_py311_generated/test_dcargs_generated.py`
- Run `pytest --backend=tyro ./tests/test_py311_generated/test_conf_generated.py`
- **Must have fewer failures than before** (or understand why not)
- Commit: "Fix TyroType in [filename]"

**Validation after each file:**

- Run core test suite
- Check failure count is decreasing
- If failures increase, debug before moving on

### Phase 4: Measure Performance

**After all tests pass:**

```bash
python benchmark_accurate.py
```

**Decision point:**

- If faster than baseline: ✅ Success!
- If same as baseline: ⚠️ No improvement, but didn't make it worse
- If slower than baseline: ❌ Failed, must debug or revert

### Phase 5: Full Test Suite

```bash
pytest --backend=tyro ./tests/test_py311_generated/ -v
```

Must have zero failures before merging.

## Risk Mitigation

### Risk 1: Performance Still Worse

**Mitigation:**

- Profile early and often
- Add timing instrumentation to specific functions
- Compare against baseline after each phase
- Be willing to stop and revert if no improvement

### Risk 2: Introduce Subtle Bugs

**Mitigation:**

- Focus on correctness first, performance second
- Write tests for previously buggy areas (narrow_subtypes, etc.)
- Review each function carefully for semantic changes
- Have multiple validation points (per-file test runs)

### Risk 3: Can't Complete Refactor

**Mitigation:**

- Have clear decision points to stop
- Commit frequently (can revert to any point)
- Don't let failed attempt linger (merge or abandon quickly)

## Open Questions

1. **Why was the previous attempt 2x slower?**

   - Need to investigate before proceeding

2. **Is reconstruction actually the bottleneck?**

   - Should profile to confirm

3. **Can TyroType comparisons/hashing be made efficient?**

   - Frozen dataclass should be fast, but verify

4. **Are there alternative approaches?**
   - Maybe caching at different boundaries?
   - Maybe lazy evaluation?

## Success Criteria

### Minimum (Required)

- ✅ All tests pass
- ✅ Performance ≥ baseline (not slower)
- ✅ No new bugs

### Target (Desired)

- ✅ Performance significantly better than baseline (>20% improvement)
- ✅ Cleaner, more maintainable code
- ✅ Fewer type-related bugs in the future

### Stretch (Ideal)

- ✅ >50% performance improvement
- ✅ Enables future optimizations (e.g., better caching)

## Decision Points

### Decision Point 1: After Phase 3

**Question:** Are tests passing and failure count decreasing?

- **Yes** → Continue to Phase 4
- **No** → Debug or consider reverting

### Decision Point 2: After Phase 4

**Question:** Is performance acceptable?

- **Faster than baseline** → Proceed to Phase 5
- **Same as baseline** → Discuss if worth keeping
- **Slower than baseline** → Debug or revert

### Decision Point 3: After Phase 5

**Question:** Are all tests passing?

- **Yes** → Ready to merge
- **No** → Fix remaining issues or revert
