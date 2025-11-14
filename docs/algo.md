
Assumptions
-----------

1. When the **lead streamer** (queue head) stops streaming, they immediately lose the front spot and must requeue if they want another turn.
2. Streamers are **never kicked** just to advance the queue—their RTMP session can stay connected while OBS switches to a different per-stream source.
3. When any non-lead streamer stops streaming they are removed from the queue.
4. Only unique stream keys can exist in the queue at any time.
5. The queue itself is the single source of truth for “who is live” and “who is next.”
6. Moderators can temporarily block the most recently disconnected lead from reclaiming the slot (useful when a timeout forcibly kicks them and OBS auto-retries).
7. The system can still force-drop a publisher (via `KICK_PUBLISHER`) when moderation or swap timing requires it; blocking ensures they cannot immediately reclaim the feed.

Simplified Motherstream Flow
----------------------------

1. **First streamer joins (on_publish)**  
   - Queue is empty ➜ enqueue streamer ➜ immediately start OBS pipeline using their dedicated RTMP URL ➜ forward their stream.

2. **Additional streamers join (on_publish)**  
   - Lead already exists ➜ enqueue new streamer if not already in queue ➜ do **not** forward them yet.

3. **Lead stops streaming (on_unpublish) or timer/health event fires**  
   - `switch_stream()` pops the current lead from the queue, stops their recording, and schedules OBS jobs to point at the next stream key.
   - If another streamer is waiting, `start_stream()` is called for that user; otherwise, OBS sources are turned off and health checks are paused.
   - The removed streamer’s key is stored so that, if blocking is enabled, an immediate reconnect attempt can be rejected.

4. **Non-lead streamer stops streaming (on_unpublish)**  
   - Remove them from whichever queue position they occupied. No other state changes are needed.

5. **Lead reconnects**  
   - Because we no longer force disconnects, reconnects are treated like a fresh publish: if the queue was empty they become the lead again (unless blocked), otherwise they rejoin at the tail after a manual `on_publish`.

6. **Forwarding decisions (on_forward)**  
   - SRS only forwards streams whose key matches `stream_queue.lead_streamer()`. Every other stream remains connected but ignored.

The result is a dramatically simpler system: the queue determines everything, OBS always switches directly between per-stream RTMP sources, and there is no additional state (`priority`, `last_stream_key`, `is_switching`, etc.) to synchronize.*** End Patch