
Assumptions:

1. If the current streamer stops streaming (on_unpublish), they lose their spot at the front
2. Once a streamer reaches the front of the queue, they will unpublish (via a kick) and are expected to republish through automatic retry mechanism in OBS
3. If a non-current streamer stops streaming, they lose their spot as well
4. Only unique stream keys join.

Motherstream algorithm


# 1. User 1 starts the stream (on_publish)                 
Current Stream: User 1, Next Stream: None, State: [User1] 
#     If there is no stream active:
    #     -> Current stream key is User 1
    #     -> forward stream to motherstream/live
# 2. User 2 enters the queue (on_publish)                  
Current Stream: User 1, Next Stream: User 2, State: [User1,User2]
#    If there is a current stream active, and the stream != User 2
        -> add user 2 to queue
        -> do not forward User 2
# 2. User 3 enters the queue (on_publish)                  
Current Stream: User 1, Next Stream: User 2, State: [User1,User2, USer3]
#    If there is a current stream active, and the stream != User 3
        -> add user 2 to queue
        -> do not forward User 2

# 3. User 1 leaves the stream or is kicked: (on_unpublish)
#    If user is the current streamer and is_switching = False
        update_state:
        -> quarantined_streamer = User 1
        -> is_switching = True
        -> current_stream_key = User 2
        -> next_stream_key = next in line                        
Current Stream: User 2, Next Stream: None, State: [User2], is_switching: True
# 3a. If User 1 kicked, OBS reconnect logic kicks in (on_publish)
#    If there is a current stream active, and the stream 
        -> add User 1 to the queue
        -> do not forward User 1
Current Stream: User 2, Next Stream: User 1, State: [User2, User1], is_switching: True
# 4. Kick User 2 to re-initiate forwarding hook (on_unpublish):
#     If user is not the current streamer and is_switching = True
        -> do not update state
        -> return
        -> set is_switching = False
Current Stream: User 2, Next Stream: User 1, State: [User2, User 1], is_switching: False
# 5. OBS reconnect logic for user 2 (on_publish)
#   If there is a current stream active and the user is the current streamer 
        -> forward the connection, and do not mess with the state at all
Current Stream: User 2, Next Stream: User 1, State: [User2, User 1], is_switching: False
# 6. User 3 enters the queue (on_publish)        
#   If there is a current stream active, and the stream != User 3
        -> add user to queue
        -> do not forward User 3       
Current Stream: User 2, Next Stream: User 1, State: [User2, User1, User 3], is_switching: False
# 7. User 2 runs out of stream time(kick) (on_unpublish):
        -> Motherstream drops User 2 as a publisher manually (via independent process).
#   If user is the current streamer and is_switching = False
        update_state:
        -> is_switching = True
        -> current_stream_key = User 1
        -> next_stream_key = User 3         
Current Stream: User 1,  Next Stream: User 3, State: [User1, User 3], is_switching: True
# 9. OBS reconnect logic for User 2 kicks in (on_publish):
#   If there is a current stream active and the user is the current streamer 
        -> forward the connection, and do not mess with the state at all
Current Stream: User 1, Next Stream: User2, State: [User1,User3]
# 4. Kick User 1 to re-initiate forwarding hook (on_unpublish):
#     If user is not the current streamer and is_switching = True
        -> do not update state
        -> set is_switching = False
        -> return
Current Stream: User 1, Next Stream: User2, State: [User1,User3]
    