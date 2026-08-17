# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false
from pathlib import Path


def load(path: Path) -> list[float]:
    import pandas as pd

    frame = pd.read_csv(path)
    frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
    series = frame.set_index("datetime")["portfolio_value"].astype(float)
    daily = series.resample("D").last().dropna()
    returns = daily.pct_change().dropna()
    return [float(value) for value in returns.to_list()]


def chart(values: list[float], out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    figure, axes = plt.subplots(figsize=(8.0, 3.5), dpi=200)
    axes.plot(range(len(values)), values, color="#77e5a2")
    axes.fill_between(range(len(values)), values, color="#245f42", alpha=0.4)
    figure.savefig(out)
    plt.close(figure)
