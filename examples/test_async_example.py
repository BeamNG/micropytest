import asyncio

async def test_async_example(ctx):
    ctx.debug("Starting async test")

    await asyncio.sleep(1)  # Simulate async operation

    ctx.debug("First async operation complete")

    await asyncio.sleep(2)  # Another async operation

    ctx.debug("Second async operation complete")

    result = await async_computation()
    ctx.debug(f"Async computation result: {result}")

    assert result == 42, "Async computation did not return expected result"

async def async_computation():
    await asyncio.sleep(1)
    return 42
