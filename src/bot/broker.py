from bot.config import settings


def build_alpaca_broker() -> object:
    api_key = settings.alpaca_api_key
    api_secret = settings.alpaca_api_secret
    if api_key is None or api_secret is None:
        raise RuntimeError("ALPACA_API_KEY and ALPACA_API_SECRET must be set")
    from lumibot.brokers import Alpaca

    configuration: dict[str, str | bool] = {
        "API_KEY": api_key.get_secret_value(),
        "API_SECRET": api_secret.get_secret_value(),
        "PAPER": settings.alpaca_is_paper,
    }
    return Alpaca(configuration)
