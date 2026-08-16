from lumibot.strategies import Strategy as LumibotStrategy


class Strategy(LumibotStrategy):
    def on_trading_iteration(self) -> None:
        if self.first_iteration:
            order = self.create_order("AAPL", 10, "buy")
            self.submit_order(order)
