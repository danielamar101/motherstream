#!/bin/bash

curl -X 'POST'  -i 'http://127.0.0.1:8483/users/'   -H 'Content-Type: application/json'   -d '{
    "email": "dan@example.com",
    "password": "ssecurepassword123",
    "stream_key": "peepeepoopoo",
    "dj_name": "kre8r",
    "ip_address": "192.168.1.100"    }'