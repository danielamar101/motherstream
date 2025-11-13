#!/bin/bash

MAX_RETRIES=5
count=0

if [ "${ENV}" = "STAGE" ]; then
    HOST="staging.motherstream.live:1937"
else
    HOST="motherstream.live"
fi

while [ $count -lt $MAX_RETRIES ]; do
    echo "Attempt $((count+1)) of $MAX_RETRIES: Starting ffmpeg stream..."
    ffmpeg -re -i $2 \
      -c:v libx264 -preset fast -crf 23 \
      -c:a aac -b:a 128k -ar 44100 -ac 2 \
      -f flv "rtmp://$HOST/live/$1?secret=always12"

    # Check the exit status of ffmpeg
    if [ $? -eq 0 ]; then
        echo "ffmpeg completed successfully."
        break
    else
        echo "ffmpeg exited with an error. Retrying in 5 seconds..."
        sleep 5
    fi

    count=$((count+1))
done

if [ $count -ge $MAX_RETRIES ]; then
    echo "Reached maximum retries ($MAX_RETRIES). Exiting."
fi

# /Users/danielamar/Desktop/Code/motherstream/scripts/stream_with_retry.sh¡