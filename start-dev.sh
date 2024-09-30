#!/bin/bash

LOG_LEVEL=debug uvicorn main:app --host 0.0.0.0 --port 8483 --reload --reload-exclude '**/*.log' --log-level debug