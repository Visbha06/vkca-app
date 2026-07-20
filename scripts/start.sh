#!/bin/bash

# Start backend and frontend in background
(cd backend && source .venv/bin/activate && uvicorn src.main:app --reload) &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

# Function to handle Ctrl+C
cleanup() {
    echo -e "\nShutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait
}

# Set trap to call cleanup on Ctrl+C (SIGINT)
trap cleanup INT

# Wait for both processes
wait