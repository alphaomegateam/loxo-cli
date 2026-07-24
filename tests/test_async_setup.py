async def test_pytest_asyncio_auto_mode_is_enabled():
    """A bare async def must be collected and run, not skipped."""
    assert True
