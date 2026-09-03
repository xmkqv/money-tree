from lumibot.strategies import Strategy as LumibotStrategy

from bot.export import StateExporter


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
