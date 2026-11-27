from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event

from app.bot.update_queue import UpdateQueue


def update(update_id, chat):
    return {"update_id": update_id, "message": {"chat": {"id": chat}}}


def test_one_slow_chat_does_not_block_others_and_offset_stays_safe():
    release_first = Event()
    first_started = Event()
    peer_finished = Event()
    next_in_chat = Event()

    def process(payload):
        if payload["update_id"] == 10:
            first_started.set()
            assert release_first.wait(5)
        elif payload["update_id"] == 11:
            next_in_chat.set()
        else:
            peer_finished.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        queue = UpdateQueue(process, executor, workers=2)
        queue.submit_updates([update(10, 1), update(11, 1)])
        queue.advance()
        try:
            assert first_started.wait(2)
            # A different chat arrives while the previous batch is still running.
            queue.submit_updates([update(10, 1), update(11, 1), update(12, 2)])
            queue.advance()
            assert peer_finished.wait(2)
            assert not next_in_chat.is_set()
            queue.pending[12].future.result(timeout=2)
            queue.advance()
            assert queue.offset == 0
        finally:
            release_first.set()
        queue.pending[10].future.result(timeout=2)
        queue.advance()
        assert queue.offset == 11
        assert next_in_chat.wait(2)
        queue.pending[11].future.result(timeout=2)
        queue.advance()
        assert queue.offset == 13
        assert not queue.pending


def test_failed_update_retries_before_next_message_from_same_user(monkeypatch):
    from app.bot import update_queue

    now = 0
    monkeypatch.setattr(update_queue, "monotonic", lambda: now)
    jobs = []

    class Executor:
        def submit(self, process, payload):
            future = Future()
            jobs.append((payload["update_id"], future))
            return future

    callback = {"update_id": 30, "callback_query": {"from": {"id": 1}}}
    queue = UpdateQueue(lambda payload: None, Executor(), workers=2)
    queue.submit_updates([callback, update(31, 1), update(32, 2)])
    queue.advance()
    assert [job[0] for job in jobs] == [30, 32]
    jobs[0][1].set_exception(RuntimeError("temporary failure"))
    jobs[1][1].set_result(None)
    assert queue.advance() == [30]
    assert queue.offset == 0
    now = 2
    queue.advance()
    assert [job[0] for job in jobs] == [30, 32, 30]
    jobs[2][1].set_result(None)
    queue.advance()
    assert queue.offset == 31
    assert jobs[-1][0] == 31
    jobs[-1][1].set_result(None)
    queue.advance()
    assert queue.offset == 33
    queue.submit_updates([update(31, 1), update(32, 2)])
    assert not queue.pending
