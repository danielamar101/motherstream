- Add uvicorn for mutiple workers (still need to configure)
- dynamic canva sheet
- Have transnition screen when no sources are active 
- ensure nginx can startup upon server reboot even when motherstream is off
- ffprobe implementation
- on_close cleanup the original streaming app. BUG: sometimes a specific stream key is just bugged and does not stream (OBS issue)?
- STATE MANAGEMENT: save queue upon server restarts


- LOOK INTO HOW NGINX WORKERS OPERATE
- Dockerize motherstream
- Fix stats page https://github.com/arut/nginx-rtmp-module/issues/975
- Get HLS streaming working
- https://github.com/arut/nginx-rtmp-module/wiki/Control-module
- https://nginx-rtmp.blogspot.com/2013/06/multi-worker-statistics-and-control.html