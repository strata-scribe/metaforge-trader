import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DealsWorker:
    def __init__(self):
        self.task = None

    async def _run(self, poll_func, get_interval_func):
        try:
            while True:
                await poll_func()
                interval = get_interval_func()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Worker task cancelled, shutting down gracefully.")
            # We can perform any cleanup if necessary here

    def start(self, poll_func, get_interval_func):
        if not self.task:
            self.task = asyncio.create_task(self._run(poll_func, get_interval_func))

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
