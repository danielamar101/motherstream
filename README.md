# Motherstream

The Motherstream is a streaming server with a queuing mechanism for incoming RTMP streams. It handles stream connections, serves as a queue manager for ffmpeg re-streaming, and provides some administrative endpoints for monitoring and control.

It is intended to be used in conjunction with nginx on a linux machine, and was originally designed to assist with automated stream management for livestreams.

## Table of Contents

1. [Introduction](#introduction)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Environment Variables](#environment-variables)
5. [API Endpoints](#api-endpoints)
6. [Queue Management](#queue-management)
7. [OBS Integration](#obs-integration)
8. [Logging](#logging)
9. [Development](#development)
10. [Contributing](#contributing)
11. [License](#license)

## Introduction

This application handles RTMP streaming with a queue mechanism, managing the re-streaming to a centralized "motherstream". It includes administrative endpoints for managing the queue and monitoring the streams. 

The application has the following main features:

- Manage a queue of incoming streams. with rtmp directive hooks.
- Start and stop the current stream.
- Persist the queue state to a file.
- Provide an HTML view of the queue.
- Integrate with OBS (Open Broadcaster Software) for scene management when a stream ends to perform cleanup events.
- WIP stream key -> DB lookup
- 

## Requirements

- Python 3.12+
- conda for environment management
- `ffmpeg` and `ffprobe` installed and available in the system PATH.
- `obsws` for OBS integration.
- direnv for environment management (See: .envrc.sample)

## Installation

1. Clone the repository:

```sh
git clone <repository_link>
cd <repository_directory>
```

2. Create a virtual environment and activate it:

```sh
conda create -f environment.yml
conda activate motherstream
```

3. Install the required dependencies:

```sh
pip install -r requirements.txt
```

4. Set up environment variables as described below.

5. Run the application:

```sh
./start-dev.sh <--- With reloading
./start.sh <-- no reloading
```

## Environment Variables

The application requires several environment variables:

- `HOST`: The streaming server host (e.g., `localhost`).
- `RTMP_PORT`: The RTMP port (e.g., `1935`).
- `OBS_HOST`: OBS WebSocket server host (e.g., `localhost`).
- `OBS_PORT`: OBS WebSocket server port (e.g., `4444`).
- `OBS_PASSWORD`: OBS WebSocket server password (optional).
- `DEBUG_PORT`: Debugging port for `debugpy` (default: `5555`).

These variables can be set in the environment or defined in a `.env` file.

## API Endpoints

- `POST /on_connect`: Triggered when a client connects to the RTMP server.
- `POST /on_publish`: Triggered when a client starts a stream.
- `POST /on_publish_done`: Triggered when a client stops a stream.
- `POST /on_done`: Triggered when a client disconnects from the RTMP server.
- `POST /override-queue`: (To be implemented) Manually override the queue.
- `GET /queue-list`: Returns an HTML page displaying the current queue.
- `GET /queue-json`: Returns the current queue as a JSON array.
- `POST /on_play`: Triggered when a client starts playing a stream.
- `POST /kill_ffmpeg`: Stops the current stream.
- `POST /clear-queue`: Clears the stream queue.

## Queue Management

The stream queue is managed using a list stored in memory and persisted to a file (`QUEUE.json`). The server periodically checks the queue, starts the next stream if no active streams are running, and removes streams from the queue when they finish.

The queue is updated using the `queue_client_stream` and `unqueue_client_stream` functions, ensuring consistency between the in-memory and persisted states.

## OBS Integration

When a stream ends, the application interacts with OBS via WebSockets to manage scenes, enabling a seamless transition between streams. The connection to OBS is configured using the `OBS_HOST`, `OBS_PORT`, and `OBS_PASSWORD` environment variables.

## Logging

FFmpeg output is logged to `ffmpeg.log`, and the application logs startup and shutdown events to standard output.

## Development

During development, the application can be run with `uvicorn` and has built-in support for `debugpy` for remote debugging.

## Contributing

Contributions are welcome! Please submit issues or pull requests to help improve the project.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.