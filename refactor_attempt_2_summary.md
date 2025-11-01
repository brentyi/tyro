# TyroType Refactor - Attempt 2 Summary

## Date
2025-11-01

## Approach
Atomic "big bang" migration: Change all type signatures at once, then fix errors.

## What We Did

### Phase 1: Infrastructure (✅ Success)
- Created `_tyro_type.py` with:
  - `TyroType` dataclass (type_origin, args, annotations)
  - `type_to_tyro_type()` - conversion to TyroType
  - `reconstruct_type_from_tyro_type()` - conversion back (expensive)
  - `tyro_type_from_origin_args()` - helper to create TyroTypes

### Phase 2: Atomic Signature Changes (✅ Success)
Changed all at once:
- `FieldDefinition.type` and `type_stripped` → TyroType
- `StructFieldSpec.type` → TyroType
- `StructTypeInfo.type` → TyroType
- `narrow_subtypes()` signature → TyroType
- `narrow_collection_types()` signature → TyroType
- `expand_union_types()` signature → TyroType

This broke tests as expected, but changes were atomic.

### Phase 3: Fix Pyright Errors (✅ Success)
Fixed 12 pyright errors by:
1. **Using `type_origin` directly for type checks** - This is the KEY win!
   - `issubclass(info.type.type_origin, SomeClass)` instead of reconstructing
   - `typ.type_origin is Union` instead of `unwrap_origin(reconstruct(typ))`
2. **Reconstructing only at boundaries**:
   - External library APIs (dataclasses, attrs, pydantic, msgspec)
   - Python type system APIs (unwrap_annotated, PrimitiveTypeInfo.make)
   - Callable boundaries (from_callable_or_type, callable_with_args)

**Critical Success**: No reconstruction in hot paths!
- ✅ `narrow_subtypes()` - uses `type_origin` directly for issubclass
- ✅ `expand_union_types()` - uses `type_origin` for isinstance checks
- ✅ `narrow_collection_types()` - works with TyroType internally

### Phase 4: Runtime Testing (❌ Failed)
Hit runtime error when running benchmark:
```
UnsupportedTypeAnnotationError: Unsupported type annotation: <function main at 0x7f7de81362a0>
```

Issue: We're creating TyroTypes where `type_origin` is `Annotated[...]` instead of extracting annotations.

## What Went Wrong

1. **Incomplete boundary identification**: Missed `PrimitiveTypeInfo.make()` call in `_arguments.py`
2. **TyroType construction issues**: Some code paths create malformed TyroTypes with Annotated as origin
3. **Testing too late**: We fixed all pyright errors before running any runtime tests
4. **No gradual validation**: All-or-nothing approach made it hard to isolate issues

## What We Learned

### ✅ Good Decisions
1. **Using `type_origin` for type checks**: This is the core performance win
   - `issubclass(typ.type_origin, ...)` instead of `issubclass(reconstruct(typ), ...)`
   - `typ.type_origin is Union` instead of complex unwrapping
2. **Clear hot path identification**: narrow_subtypes, expand_union_types, narrow_collection_types
3. **Boundary-only reconstruction**: All 18 reconstruction sites were at legitimate boundaries
4. **Cached boundaries**: Functions like `StructTypeInfo.make()` are cached, so reconstruction happens once per type

### ❌ Problems
1. **Big bang approach**: Changed everything at once, hard to debug
2. **Late testing**: Should have run simple tests after each phase
3. **No fallback**: Once we started, couldn't revert to working state incrementally
4. **TyroType validation**: Need better validation that TyroTypes are well-formed (annotations extracted, not in type_origin)

## Lessons for Next Attempt

### Use Parallel Implementation

#### Option A: Parallel Data Fields
Keep both type representations in dataclasses:
```python
@dataclasses.dataclass
class FieldDefinition:
    intern_name: str
    extern_name: str
    type: TypeForm[Any]  # OLD - keep working
    tyro_type: TyroType | None = None  # NEW - gradually populate
    type_stripped: TypeForm[Any]  # OLD - keep working
    tyro_type_stripped: TyroType | None = None  # NEW - gradually populate
    # ... rest of fields

    def get_type(self) -> TyroType:
        """Get type as TyroType, converting if needed."""
        if self.tyro_type is not None:
            return self.tyro_type
        return type_to_tyro_type(self.type)
```

Benefits:
- Gradual migration: populate `tyro_type` field by field
- Always have fallback to working `type` field
- Can validate both match during transition
- Easy to measure performance impact incrementally

#### Option B: Parallel Functions
Keep both implementations side-by-side:
```python
# Old path (working)
def narrow_subtypes_OLD(typ: TypeForm, default: Any) -> TypeForm:
    # Current working implementation
    ...

# New path (being developed)
def narrow_subtypes_NEW(typ: TyroType, default: Any) -> TyroType:
    # TyroType-based implementation
    ...

# Wrapper that uses new path, falls back to old
def narrow_subtypes(typ: TypeForm | TyroType, default: Any) -> TypeForm | TyroType:
    if isinstance(typ, TyroType):
        return narrow_subtypes_NEW(typ, default)
    else:
        return narrow_subtypes_OLD(typ, default)
```

**Recommendation**: Use Option A (parallel fields) for dataclasses, Option B (parallel functions) for hot path functions.

### Gradual Migration Path
1. Add TyroType infrastructure (same as before)
2. Add parallel `*_NEW()` functions for hot paths
3. Add wrapper functions that dispatch to old/new
4. **Test after each function** - don't wait!
5. Migrate call sites one at a time
6. Once all migrated, remove old functions

### Validation Points
- After each parallel function: Run simple unit test
- After each hot path: Run benchmark on that path
- After each struct rule: Run tests for that struct type
- Continuous validation, not end-to-end at the finish

### TyroType Validation
Add validation to `TyroType.__post_init__()`:
```python
def __post_init__(self):
    # Ensure annotations are extracted, not in type_origin
    from typing import get_origin
    from typing_extensions import Annotated
    if get_origin(self.type_origin) is Annotated:
        raise ValueError(f"TyroType.type_origin should not be Annotated[...]. "
                        f"Extract annotations first. Got: {self.type_origin}")
```

## Performance Analysis

### Expected Wins
The hot paths that we successfully converted:
1. `narrow_subtypes()` - called on every field during type narrowing
2. `expand_union_types()` - called when handling defaults
3. `narrow_collection_types()` - called on collection types

These no longer reconstruct types! They use `type_origin` directly.

### Expected Cost
Reconstruction at 18 boundary sites, but these are:
- One-time per type (cached in `StructTypeInfo.make()`)
- Necessary for external APIs (dataclasses, attrs, etc.)
- Not in hot loops

### Cannot Validate Yet
We didn't get to run benchmarks due to runtime error.

## Files Changed
- ✅ `_tyro_type.py` - New infrastructure (working)
- ✅ `_fields.py` - TyroType support (working)
- ✅ `_resolver.py` - Hot paths use type_origin (working)
- ✅ `_arguments.py` - TyroType support (partial - runtime error)
- ✅ `_calling.py` - TyroType support (working in pyright)
- ✅ `_parsers.py` - TyroType support (working in pyright)
- ✅ `constructors/_struct_spec*.py` - TyroType support (working in pyright)

## Commits Made
1. Phase 1: Add TyroType infrastructure
2. Phase 2: Change all type signatures atomically
3. Hot path fixes: Eliminate reconstruction from narrow_subtypes, expand_union_types
4. Phase 3: Fix all pyright errors with minimal reconstruction

## Recommendation

Start over with parallel approach:
- Keep working code untouched
- Build TyroType path alongside
- Test continuously
- Migrate gradually
- Remove old code only at the end

This will take longer but be much safer and easier to debug.

## Quick Wins to Preserve

When starting the parallel approach, remember these key insights:
1. Use `typ.type_origin` for `issubclass()` and `isinstance()` checks
2. Use `typ.type_origin is Union` instead of complex unwrapping
3. Only reconstruct at true boundaries (external APIs, Python type system)
4. All hot paths: narrow_subtypes, expand_union_types, narrow_collection_types
5. Validate TyroTypes are well-formed (no Annotated in type_origin)
