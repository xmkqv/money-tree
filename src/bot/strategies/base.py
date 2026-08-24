from importlib import import_module

from lumibot.strategies import Strategy as LumibotStrategy

from bot.export import StateExporter
from bot.types import StrategyName


class StrategyBase(LumibotStrategy):
    exporter: StateExporter | None = None

    def on_bot_crash(self, error: Exception) -> None:
        if self.exporter is not None:
            self.exporter.publish("failed", "crash", "error", type(error).__name__)

    def on_abrupt_closing(self) -> None:
        if self.exporter is not None:
            self.exporter.close("stopped", "Trading run stopped")

    def on_strategy_end(self) -> None:
        self.on_abrupt_closing()


def load_strategy(name: StrategyName) -> type[StrategyBase]:
    strategy_class = import_module(f"bot.strategies.{name}").Strategy
    if not isinstance(strategy_class, type) or not issubclass(strategy_class, StrategyBase):
        raise TypeError(f"bot.strategies.{name}.Strategy must subclass StrategyBase")
    return strategy_class
