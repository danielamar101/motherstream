

Case 1: 
    - No one is in the queue and block toggle not set
        - Last stream doesnt matter
    - Forward
    - Enqueue
    - State: [User]
Case 2:
    - No one is in the queue and block toggle is set
        - Last stream is the one trying to join
    - Do Not Forward
    - State: []
Case 3:
    - No one is in the queue and the block toggle is set
        - Last stream key is not the one trying to join
    - Forward
    - Enqueue
    - State: [User]
Case 4 (User 1) redoes flow due to starting kick. They were the current streamer. State was [User 1, User 2]:
    - Unpublish flow
        - Do not change state
        - disable PRIORITY behavior
    
    - then publish flow
        - User 1 is in the queue (front)
        - Forward
        - Do not enqueue
        - State: [User 1, User 2]
Case 5 (User 2) redoes flow due to timeout kick. They were the current streamer. State was [User 2, User 3]:
    -  Unpublish flow.
        - dequeue User 2
        - Remember User 2 was our last streamer (for block toggle ability)
        - enable PRIORITY behavior

    -OBS triggers publish flow
        - User 2 is not our current streamer
        - Enqueue
        - Do Not Forward
        - State: [User 3, User 2]
    - User 3 performs Case 4
Case 6 (User 2) unpublishes flow due to manually leaving. They were the current streamer. State was [User 2, User 3]:
    -  Unpublish flow.
        - dequeue User 2
        - Remember User 2 was our last streamer (for block toggle ability)
        - enable PRIORITY behavior
    - User 3 Performs case 4

Case 7 (User 1) joins the queue. They are not the current streamer. State is [User 2, User 3]:
    - Publish flow
        - queue User 1
        - Do Not Forward
        - State: [User 2, User 3, User 1]

PRIORITY is how we will track the kicked user 
LAST_STREAMER is how we will track the previous streamer
BLOCKING is how we will track whether or not we will allow the previous streamer to reconnect and restream

Note: Last streamer and priority streamer should always be distinct!

Unpublish:
  if PRIORITY:
    -> Unpublish has already executed by Case 5 or 6. This means current Unpublish is due to starting kick (case 4).
    - Do not change state
    - Disable PRIORITY
  else:
    -> Unpublish is being executed by Case 5 or 6
    if the caller is the lead streamer:
      - enable PRIORITY
      - LAST_STREAMER is caller
    - remove the caller (remove_client_with_stream_key)
  
Publish:
  if no one is in the queue:
    if there was a last streamer:
      if BLOCKING and last streamer is caller:
        - Do Not Forward
      else:
        - forget LAST_STREAMER 
        - queue up caller
        - Start stream
        - Forward
    else:
      - queue up caller
      - Start Stream
      - Forward
  # Someone must be in the queue
  if the caller is the current streamer:
    - Forward 
    - Do not queue
  else: 
      - queue up caller
      - Do not forward



