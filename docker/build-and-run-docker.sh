#!/bin/bash
docker build -t motherstream .

docker run -d --name motherstream -p 8483:8483 motherstream