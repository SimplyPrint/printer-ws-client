import threading


class Synchronized:
    __lock: threading.Lock

    def __init__(self, *args, **kwargs):
        self.__lock = threading.Lock()

    def __enter__(self):
        self.__lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__lock.release()
