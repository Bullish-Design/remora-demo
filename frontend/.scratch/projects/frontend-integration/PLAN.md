# Frontend Integration — Plan

**ABSOLUTE RULE: NEVER use subagents (the Task tool). Do all work directly.**

---

## Goal

Relocate the Remora graph viewer from the main remora repo to a standalone Stario-based webapp in remora-demo/frontend/.

## Phases

### Phase 1: Build in remora repo (DONE)
Build and test all graph viewer modules in remora repo under `remora_demo/web/graph/`. All 130 tests pass.

### Phase 2: Relocation to remora-demo (DONE)
1. [DONE] Copy all 13 source files to `frontend/graph/` with import rewrites (`remora_demo.web.graph.*` -> `graph.*`)
2. [DONE] Copy all 8 test files to `frontend/tests/` with import rewrites
3. [DONE] Update pyproject.toml for `graph` package
4. [DONE] Update devenv.nix scripts
5. [DONE] Write launch.sh
6. [DONE] Run full test suite — 132 passed, 0 skipped, 0 failures

### Phase 3: Backend Integration (FUTURE)
- Wire frontend to actual backend services
- Set up DB provisioning / demo data
- End-to-end testing with real Remora backend

---

**REMINDER: NEVER use the Task tool. Do all work directly.**
