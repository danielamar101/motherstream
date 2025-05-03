#!/bin/bash

LOG_LEVEL=debug \
opentelemetry-instrument \
uvicorn main:app --host 0.0.0.0 --port 8483 --reload-exclude '**/*.log' --log-level debug