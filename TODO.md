- Add uvicorn for mutiple workers (still need to configure)
- dynamic canva sheet
- Have transnition screen when no sources are active 
- on_close cleanup the original streaming app. BUG: sometimes a specific stream key is just bugged and does not stream (OBS issue)?
- STATE MANAGEMENT: save queue upon server restarts


- Dockerize motherstream
- Get HLS streaming working
- https://github.com/arut/nginx-rtmp-module/wiki/Control-module
- https://nginx-rtmp.blogspot.com/2013/06/multi-worker-statistics-and-control.html

- Parse XML stat page to detect if motherstream/live is being published to: https://docs.python.org/3/library/xml.etree.elementtree.html