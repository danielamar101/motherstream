from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import APIRouter

from main import process_manager

http_blueprint = APIRouter()

@http_blueprint.get('/queue-json')
async def queue_json():
        stream_queue = process_manager.stream_queue.get_dj_name_queue_list()
        return JSONResponse(content=stream_queue)


@http_blueprint.get("/queue-list",response_class=HTMLResponse)
async def queue_list():
    return f"""
    <html>
        <head>
            <title>Queue</title>
            <meta http-equiv="refresh" content="10">
            <style>
                body {{ color: white; font-family: Arial, sans-serif; }}
                ul {{ list-style: none; padding-left: 20px; }}
                li {{ color: white; margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <h1>Queue</h1>
            <h5 id="next-up">Now Playing:</h5>
            <h5>Next up:</h5>
            <div id="queue-list">
                <!-- The list will be rendered here -->
            </div>
            <script>
                async function fetchQueue() {{
                    try {{
                        const response = await fetch('http://192.168.1.100:8483/queue-json');
                        const data = await response.json();
                        const queueList = document.getElementById('queue-list');
                        const nowPlaying = document.getElementById('next-up');
                        
                        // Clear the current list
                        queueList.innerHTML = '';
                        nowPlaying.textContent = 'Now Playing:';

                        // Create a new unordered list element
                        const ul = document.createElement('ul');

                        if (data.length === 0) {{
                            queueList.innerHTML = '<p>The queue is empty.</p>';
                        }}
                        if (data.length > 0) {{
                            nowPlaying.textContent = `Now Playing: ${{data[0]}}`;
                            // Iterate over the JSON data and create list items


                            data.forEach((item,index) => {{
                                if (index !== 0) {{
                                    const li = document.createElement('li');
                                    li.textContent = item;
                                    ul.appendChild(li);
                                }}
                            }});
                        }}

                        // Append the new list to the div
                        queueList.appendChild(ul);
                    }} catch (error) {{
                        console.error('Error fetching queue:', error);
                    }}
                }}

                // Fetch and render the queue immediately
                fetchQueue();

                // Refresh the queue every 10 seconds
                setInterval(fetchQueue, 10000);
            </script>
        </body>
    </html>
    """

@http_blueprint.post("/override-queue")
async def override_queue_manually(
    *args,
    **kwarg
):
    pass


@http_blueprint.post("/kill_ffmpeg")
async def kill_ffmpeg():
    process_manager.stop_current_stream()
    return JSONResponse(status_code=200,content={"message": "stopped current stream"})

@http_blueprint.post("/clear-queue")
async def clear_queue():
    
    return JSONResponse(status_code=200, content={"message": "cleared queue."})


