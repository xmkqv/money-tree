from bot.config import settings


def build_alpaca_broker() -> object:
    if settings.alpaca_api_key is None or settings.alpaca_api_secret is None:
        raise RuntimeError("ALPACA_API_KEY and ALPACA_API_SECRET must be set")
    from lumibot.brokers import Alpaca

    configuration = {
        "API_KEY": settings.alpaca_api_key.get_secret_value(),
        "API_SECRET": settings.alpaca_api_secret.get_secret_value(),
        "PAPER": settings.alpaca_is_paper,
    }
    return Alpaca(configuration)
