import pytest

from mt.strategies.order_tag import ORDER_TAG_PREFIX, OrderTag, find_order_tag, order_tag
from tests.world.index import check
from tests.world.types import Case, World


def round_trips_when_well_formed(world: World) -> None:
    tag = order_tag("breakout_5m", "e", "AAPL", 0.0125)
    assert find_order_tag(tag) == OrderTag("breakout_5m", "e", "AAPL", 0.0125)


def is_none_when_prefix_differs(world: World) -> None:
    tag = order_tag("daily_sma", "x", "MSFT", 0.005).replace(f"{ORDER_TAG_PREFIX}-", "xx-", 1)
    assert find_order_tag(tag) is None


def is_none_when_code_is_unknown(world: World) -> None:
    assert find_order_tag(f"{ORDER_TAG_PREFIX}-?-e-AAPL-12500-deadbeef") is None


CASES = [
    Case(
        "round_trips_when_well_formed",
        "a tag reads back its strategy, kind, symbol, and risk fraction",
        round_trips_when_well_formed,
    ),
    Case(
        "is_none_when_prefix_differs",
        "a tag without the prefix is not ours",
        is_none_when_prefix_differs,
    ),
    Case(
        "is_none_when_code_is_unknown",
        "a tag with an unknown strategy code is not ours",
        is_none_when_code_is_unknown,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[case.key for case in CASES])
def test(case: Case) -> None:
    check(case)
