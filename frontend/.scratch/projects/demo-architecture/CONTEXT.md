# CONTEXT: DEMO_ARCHITECTURE.md Revision (Round 2 Audit)

## Current State

**PROJECT COMPLETE — Round 2 audit finished.**

The full audit of `DEMO_ARCHITECTURE.md` against the current Remora library source code is done. All discrepancies have been identified and fixed.

## What Was Done in Round 2

Audited the entire 3158-line document against every source file in the refactored Remora library. Found and fixed 11 discrepancies:

### Critical Fixes (type errors in code blocks)
1. **CSTNode** described as `@dataclass(frozen=True, slots=True)` → actually `class CSTNode(BaseModel)` with `ConfigDict(frozen=True)` and custom `__hash__` by `node_id` only
2. **SubscriptionPattern** described as `@dataclass` → actually `class SubscriptionPattern(BaseModel)`
3. **ToolSchema** described as "a dataclass" → actually `class ToolSchema(BaseModel)`
4. **`to_row()` code** showed `asdict(t) if is_dataclass(t)` → actual code uses `t.model_dump()`

### Factual Corrections
5. **parse_file()** was claimed to be "Used by ASTWatcher" → ASTWatcher has its own `_parse_file_only()` method
6. **EventBus `clear()` method** was undocumented
7. **Section 9.4 routes** showed `/graph`, `/sidebar`, `/stream` → actual routes are `/subscribe`, `/agent/*`, `/events`, `/command`
8. **Section 9.4** claimed "never writes to database" → contradicted by `push_command()` write path

### Minor Fixes
9. Section 8.3 `pattern_json` described as "dataclass" → "Pydantic BaseModel"
10. Section 7.4 "List and dataclass fields" → "List and nested Pydantic model fields"
11. Line number references updated (to_row, from_row, to_system_prompt)

## Document Structure (unchanged)

| Section | Title | Lines (approx) |
|---------|-------|----------------|
| 1 | System Overview | ~80 |
| 2 | Remora Core Architecture | ~760 |
| 3 | The Data Flow Pipeline | ~200 |
| 4 | Neovim Demo Architecture | ~450 |
| 5 | Web Demo Architecture | ~250 |
| 6 | Graph Viewer Architecture | ~300 |
| 7 | Crossover Interfaces | ~350 |
| 8 | Unified SQLite Database | ~200 |
| 9 | Startup & Lifecycle | ~430 |

## File Locations

- Target: `/home/andrew/Documents/Projects/remora-demo/DEMO_ARCHITECTURE.md`
- Remora source: `/home/andrew/Documents/Projects/remora/src/remora/`
- remora_demo: `/home/andrew/Documents/Projects/remora/remora_demo/`
- Frontend: `/home/andrew/Documents/Projects/remora-demo/frontend/`
