# Remora Demo (Stario)

This repo contains a fresh, two-process demo app:

- **Frontend (Python 3.14)**: Stario UI at `http://127.0.0.1:8000`
- **Backend (Python 3.13)**: Remora chat service at `http://127.0.0.1:8420`

The split is required because Remora and Stario target different Python versions.

## Quick Start

1. Create the backend environment (Python 3.13):

```bash
python3.13 -m venv .venv-backend
source .venv-backend/bin/activate
pip install -e backend
```

2. Create the frontend environment (Python 3.14):

```bash
python3.14 -m venv .venv-frontend
source .venv-frontend/bin/activate
pip install -e frontend
```

3. Start both services (from their devenv shells):

```bash
# backend shell
start-backend

# frontend shell
start-frontend
```

## Notes

- The backend expects an OpenAI-compatible model server at `http://localhost:8000/v1`.
- Sessions are in-memory and reset on restart.
- Tool telemetry is streamed live into the UI tool log.

## Repo Layout

```
backend/     # Remora chat service (Python 3.13)
frontend/    # Stario UI (Python 3.14)
scripts/     # Start scripts
.context/    # Remora + Stario sources (local dependencies)
```
