# Swarm Study — Context

## Current State
COMPLETE. The analysis has been written to SWARM_ARCHITECTURE.md.

The user asked: "Do we need the swarm layer? Can the event system do it all?"

Answer: The event system provides the essential architecture. The swarm layer
adds ~2,800 lines of complexity for a "every code element = agent" paradigm
that can be replaced by a thin execution layer (~200 lines) on top of the
event system.

## Output File
`/home/andrew/Documents/Projects/remora-demo/SWARM_ARCHITECTURE.md`

## Key Finding
- Event system: ~1,400 lines, provides event sourcing, routing, projections, streaming
- Swarm layer: ~2,800 lines, adds discovery, dual execution paths, cascade prevention, per-agent workspaces
- The swarm layer is fully replaceable by a thin handler + simpler registration
