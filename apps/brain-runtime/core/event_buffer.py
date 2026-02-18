import time

class EventBuffer:
    def __init__(self, max_size=300):
        self.events = []
        self.max_size = max_size

    def push(self, event):
        if not event:
            return
        self.events.append(event)
        while len(self.events) > self.max_size:
            self.events.pop(0)

    def get_recent(self, ms):
        """
        Returns events from the last 'ms' milliseconds.
        """
        cutoff = (time.time() * 1000) - ms
        return [e for e in self.events if e.get("ts", 0) >= cutoff]

    def get_all(self):
        return self.events

