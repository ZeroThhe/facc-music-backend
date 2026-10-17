import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._subs = defaultdict(set)  # tema -> {(loop, cola)}

    def publish(self, tema, payload):
        for loop, cola in list(self._subs[tema]):
            loop.call_soon_threadsafe(cola.put_nowait, payload)

    async def subscribe(self, tema):
        entrada = (asyncio.get_running_loop(), asyncio.Queue())
        self._subs[tema].add(entrada)
        try:
            while True:
                yield await entrada[1].get()
        finally:
            self._subs[tema].discard(entrada)


bus = EventBus()