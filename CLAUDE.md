COMMON COMMANDS:

OBS_HOST=dedicated OBS_PORT=4455 OBS_PASSWORD=YrHUIvJTCREGyD19 python check_obs_output_health.py
sudo docker logs --follow motherstream-prod --tail 1000
sudo ./stop-all.sh && sudo ./start-all.sh
watch -t -n 1 'curl -L -s http://motherstream.live/backend/stream-health/current | jq .'
python network_monitor.py 
python analyze_gstreamer_health.py 

WHEN DEALING WITH PYTHON, BE SURE TO SOURCE ENVIRONMENT:

source <root dir>/.venv/bin/activate

Remember the Motherstream exists as a dockerized application. It runs in both staging and production.
When developing and testing remember to use these dockerized environments. The top level directory has relevant dockerfiles.