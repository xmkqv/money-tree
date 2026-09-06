from .config import settings


def alpaca_broker() -> object:
    from lumibot.brokers import Alpaca

    configuration: dict[str, str | bool] = {
        "API_KEY": settings.broker.api_key.get_secret_value(),
        "API_SECRET": settings.broker.api_secret.get_secret_value(),
        "PAPER": settings.broker.mode == "paper",
        "MARKET": "NYSE",
    }
    return Alpaca(configuration)
