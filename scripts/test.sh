#!/bin/bash

(echo "BACKEND TESTS")
(cd backend/ && source .venv/bin/activate && uv sync --group test && VKCA_ENV=test pytest -q --tb=short)
(echo "------")
(echo "FRONTEND TESTS")
(cd frontend/ && npm test -- --silent --reporter=dot)
(echo "------")
(echo "E2E TESTS")
(cd frontend/ && npm run test:e2e -- --reporter=dot)
