ffmpeg -re -i C1C3LMPFH8-02-16-19-35.flv \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k -ar 44100 -ac 2 \
  -f flv "rtmp://always12.duckdns.org/live/9A3DMIMKXK?secret=always12"

ffmpeg -re -i C1C3LMPFH8-02-16-19-35.flv \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k -ar 44100 -ac 2 \
  -f flv "rtmp://always12.duckdns.org/live/LRWDXHYO9O?secret=always12"

ffmpeg -re -i C1C3LMPFH8-02-16-19-35.flv \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k -ar 44100 -ac 2 \
  -f flv "rtmp://always12.duckdns.org/live/10UA0U6LPC?secret=always12"