from mt.rules.shared import settings


def broker_credentials(*, paper: bool) -> dict[str, str | bool]:
    key, secret = settings.broker.key_pair
    return {"API_KEY": key, "API_SECRET": secret, "PAPER": paper}


def alpaca_broker() -> object:
    from lumibot.brokers import Alpaca

    credentials = broker_credentials(paper=settings.broker.is_paper)
    return Alpaca({**credentials, "MARKET": "NYSE"})
