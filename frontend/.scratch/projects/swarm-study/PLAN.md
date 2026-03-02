# Swarm Study — Plan

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

## Goal

Produce a comprehensive, detailed report on the Remora Swarm system architecture
by reading every relevant source file from disk and synthesizing findings into a
single document: `SWARM_ARCHITECTURE.md` at the remora-demo root.

## Approach

1. Read ALL source files in `/home/andrew/Documents/Projects/remora/src/remora/`
2. Write the report section-by-section, appending to file as we go
3. Every claim references a specific `file:line` location

## Sections

1. Executive Summary & Conceptual Model
2. Discovery & Reconciliation
3. Event Sourcing Architecture
4. Subscription & Routing System
5. Execution Layer (AgentRunner & SwarmExecutor)
6. Agent Model & Identity
7. Communication & Tools
8. Workspace & File System
9. Extension System
10. Service & UI Layer
11. CLI Entry Points & Operational Modes
12. Cascade Prevention & Safety
13. End-to-End Reactive Loop Walkthrough
14. Data Flow Diagrams
15. Cross-Cutting Concerns & Design Decisions

## Output

`/home/andrew/Documents/Projects/remora-demo/SWARM_ARCHITECTURE.md`

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
