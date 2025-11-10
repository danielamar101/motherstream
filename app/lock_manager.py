import threading

# Use RLock (reentrant lock) for queue operations to allow nested locking by the same thread
lock = threading.RLock()

obs_lock = threading.Lock()

state_lock = threading.Lock()  # For StreamManager state variables