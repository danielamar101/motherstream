#!/bin/bash

sudo docker run --rm -it -p 2022:2022 -p 443:2443 -p 1937:1935 \
  -p 8080:8080 -p 8000:8000/udp -p 10080:10080/udp --name oryx \
  -v /home/danielamar/Desktop/onyx:/data ossrs/oryx:5