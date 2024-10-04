#!/bin/bash

curl -X 'POST'  -i 'http://127.0.0.1:8483/users/'   -H 'Content-Type: application/json'   -d '{
    "email": "dan2@example.com",
    "password": "ssecurepsassword123",
    "stream_key": "culprit",
    "dj_name": "culprit",
    "ip_address": "192.168.1.100"    }'