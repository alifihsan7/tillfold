from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from time import monotonic
from typing import Callable


def _chat_key(update: dict) -> int | None:
    callback = update.get("callback_query") or {}
    message = update.get("message") or {}
    # Receipt callbacks in a group and private commands from the same owner share a queue.
    return (callback.get("from") or {}).get("id") or (message.get("chat") or {}).get("id")


@dataclass
class _Pending:
    update: dict
    chat: int | None
    future: Future | None = None
    done: bool = False
    attempts: int = 0
    ready_after: float = 0


class UpdateQueue:
    def __init__(self, process: Callable[[dict], None], executor: ThreadPoolExecutor, workers: int):
        self.offset = 0
        self.pending: dict[int, _Pending] = {}
        self._process = process
        self._executor = executor
        self._workers = workers

    def submit_updates(self, updates: list[dict]) -> None:
        for update in sorted(updates, key=lambda item: item["update_id"]):
            update_id = update["update_id"]
            if update_id >= self.offset and update_id not in self.pending:
                self.pending[update_id] = _Pending(update, _chat_key(update))

    def advance(self) -> list[int]:
        now = monotonic()
        failed = []
        for update_id, item in self.pending.items():
            if not item.future or not item.future.done():
                continue
            error = item.future.exception()
            item.future = None
            if error is None:
                item.done = True
            else:
                item.attempts += 1
                item.ready_after = now + min(30, 2 ** min(item.attempts, 5))
                failed.append(update_id)

        # Advancing the offset confirms every lower message to Telegram.
        # Keep it behind any outstanding update, including a retry.
        while self.pending:
            first = next(iter(self.pending))
            if not self.pending[first].done:
                break
            del self.pending[first]
            self.offset = first + 1

        active = sum(item.future is not None for item in self.pending.values())
        seen_chats = set()
        for item in self.pending.values():
            if active == self._workers:
                break
            if item.done or item.chat in seen_chats:
                continue
            seen_chats.add(item.chat)
            if item.future is None and item.ready_after <= now:
                item.future = self._executor.submit(self._process, item.update)
                active += 1
        return failed
