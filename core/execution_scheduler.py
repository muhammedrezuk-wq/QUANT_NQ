from __future__ import annotations

import asyncio
import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable


class ExecutionScheduler:
    """Separates handler execution from the EventBus coordination loop."""

    def __init__(self, *, max_workers: int = 32, thread_name_prefix: str = "quant-handler") -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=thread_name_prefix)

    @staticmethod
    def _invoke_sync(handler: Callable[..., Any], args: tuple[Any, ...]) -> Any:
        result = handler(*args)
        if inspect.isawaitable(result):
            return asyncio.run(result)
        return result

    async def run(self, handler: Callable[..., Any], *args: Any, timeout_s: float | None = None) -> Any:
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._pool, self._invoke_sync, handler, args)
        if timeout_s is None:
            return await future
        return await asyncio.wait_for(future, timeout=timeout_s)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        self._pool.shutdown(wait=wait, cancel_futures=cancel_futures)
