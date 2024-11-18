
Motherstream algorithm


# 1. User 1 starts the stream (on_publish)                 
Current Stream: User 1, Last Stream: None, Next Stream: None, State: [User1] 
#     If user wasnt the last streamed key
    #     -> Current stream key is User 1
    #     -> forward stream to motherstream/live
# 2. User 2 enters the queue (on_publish)                  
Current Stream: User 1, Last Stream: None, Next Stream: User 2, State: [User1,User2]
#    If there is a current stream active, and the stream != User 2
        -> add user to queue
        -> do not forward User 2
# 3. User 1 leaves the stream or is kicked: (on_unpublish)
#    If user is the current streamer and is_switching = False
        update_state:
          -> is_switching = True
    #     -> current_stream_key = User 2
    #     -> next_stream_key = None                        
Current Stream: User 2, Next Stream: None, State: [User2], is_switching: True
# 3a. If User 1 kicked, OBS reconnect logic kicks in (on_publish)
#    If there is a current stream active, and the stream != User 1
        -> add User 1 to the queue
        -> do not forward User 1
Current Stream: User 2, Next Stream: User 1, State: [User2, User1], is_switching: True
# 4. Kick User 2 to re-initiate forwarding hook (on_unpublish):
#     If user is not the current streamer and is_switching = True
        -> do not update state
        -> return
        -> set is_switching = False
Current Stream: User 2, Next Stream: User 1, State: [User2, User 1]
# 5. OBS reconnect logic for user 2 (on_publish)
# on_publish hook gets triggered again
#   If there is a current stream active and the user is the current streamer 
    -> forward the connection, and do not mess with the state at all
Current Stream: User 2, Next Stream: User 1, State: [User2, User 1]
# 6. User 1 enters the queue (on_publish hook)               
Current Stream: User 2, Last Stream: None, Next Stream: User1, State: [User2, User1]
        -> User 2 is streaming to motherstream/live,
        -> So no forward is allowed
# 7. User 2 runs out of stream time:
        -> Motherstream drops User 2 as a publisher manually.
        -> Stream state is updated to prevent User 2 OBS re-connect logic
        -> In this case keep Last Stream variable populated
Current Stream: User 1, Last Stream: User 2, Next Stream: None, State: [User1], Manually Kicked: True
# 8. on_unpublish hook hits bc User 2 is kicked out
#    -> if user is the current streamer and was not manually kicked:
#       (pass bc it was manually kicked)
#    -> if user was the last streamer:
#        -> Remove Last Stream value, do not change the queue state as the user is not in there
# 9. OBS reconnect logic for User 2 kicks in:
# -> User 2 is added to the back of the queue
Current Stream: User 1, Last Stream: None, Next Stream: User2, State: [User1,User2]

Update stream state(user=None):
    1. If there is no current streamer:
        Add the next streamer to the queue
        Update state
            Current Streamer: user, Next Streamer: None, Last Streamer: None
    2. If there is a current streamer:
        Remove the current streamer from queue
        Update State
            Current Streamer: Next in queue, Next Streamer: Non 
    