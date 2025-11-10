import threading

lock = threading.Lock()

obs_lock = threading.Lock()

state_lock = threading.Lock()  # For StreamManager state variables