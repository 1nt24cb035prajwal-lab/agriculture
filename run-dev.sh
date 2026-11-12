#!/usr/bin/env bash
# Starts backend (:8000) and frontend (:5173). Run setup first (see README).
set -e
(cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &
wait
