from mt.config.bot import settings


def broker_credentials(*, paper: bool) -> dict[str, str | bool]:
    return {
        "API_KEY": settings.broker.api_key.get_secret_value(),
        "API_SECRET": settings.broker.api_secret.get_secret_value(),
        "PAPER": paper,
    }


def alpaca_broker() -> object:
    from lumibot.brokers import Alpaca

    credentials = broker_credentials(paper=settings.broker.mode == "paper")
    return Alpaca({**credentials, "MARKET": "NYSE"})
