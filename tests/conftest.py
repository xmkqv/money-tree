from collections.abc import Iterator

import pytest

from tests.world.setup import setup, teardown


@pytest.fixture(scope="session", autouse=True)
def world() -> Iterator[None]:
    setup()
    yield
    teardown()
