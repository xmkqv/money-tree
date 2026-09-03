from .config import settings


def build_alpaca_broker() -> object:
    from lumibot.brokers import Alpaca

    configuration: dict[str, str | bool] = {
        "API_KEY": settings.alpaca_api_key.get_secret_value(),
        "API_SECRET": settings.alpaca_api_secret.get_secret_value(),
        "PAPER": settings.alpaca_is_paper,
    }
    return Alpaca(configuration)
