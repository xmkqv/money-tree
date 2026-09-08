import logging

from .types import Case, World


logger = logging.getLogger(__name__)


def init() -> World:
    return World()


def check(case: Case) -> None:
    logger.info("%s — %s", case.key, case.claim)
    case.check(init())
