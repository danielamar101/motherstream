#!/bin/bash

LOG_LEVEL=info uvicorn main:app --host 0.0.0.0 --port 8483 --log-config=logging_config.yml