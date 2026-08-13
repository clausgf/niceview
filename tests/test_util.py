import asyncio
import functools

import pytest

from niceview.util import maybe_await


class TestMaybeAwait:
    async def test_passes_a_plain_value_through(self):
        assert await maybe_await(42) == 42

    async def test_passes_none_through(self):
        assert await maybe_await(None) is None

    async def test_awaits_a_coroutine(self):
        async def produce() -> str:
            await asyncio.sleep(0)
            return 'done'

        assert await maybe_await(produce()) == 'done'

    async def test_awaits_a_future(self):
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        future.set_result('done')
        assert await maybe_await(future) == 'done'

    async def test_propagates_the_handlers_exception(self):
        async def fail() -> None:
            raise ValueError('boom')

        with pytest.raises(ValueError, match='boom'):
            await maybe_await(fail())

    async def test_a_sync_handler_has_already_run_by_the_time_we_await(self):
        # The point of the sync path: calling the handler is what has the effect, and that
        # happened at the call site. maybe_await only has a return value left to pass on.
        calls: list[int] = []

        def handler() -> int:
            calls.append(1)
            return len(calls)

        result = handler()
        assert calls == [1]
        assert await maybe_await(result) == 1

    async def test_awaits_an_async_functools_partial(self):
        # functools.partial of an async function is not itself a coroutine function, but calling
        # it still yields a coroutine -- maybe_await inspects the result, not the callable.
        async def add(a: int, b: int) -> int:
            return a + b

        assert await maybe_await(functools.partial(add, 1)(2)) == 3
