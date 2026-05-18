"""Метрики качества модели: WAPE, MAE, RMSE и калибровка квантилей."""
from __future__ import annotations

import numpy as np
import pandas as pd


def wape(y_true: pd.Series, y_pred: pd.Series) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    denom = np.sum(np.abs(y_true))
    if denom == 0:
        return float("nan")
    return float(np.sum(np.abs(y_true - y_pred)) / denom * 100)


def mae(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def quantile_coverage(
    y_true: pd.Series, y_pred_quantile: pd.Series
) -> float:
    """Доля наблюдений, в которых факт <= прогнозного квантиля.

    Если для q90 фактическое покрытие отклоняется от 0.90 более чем на 5 п.п.,
    калибровка квантильной модели нарушена и страховой запас будет смещён.
    """
    y_true, y_pred_quantile = np.asarray(y_true), np.asarray(y_pred_quantile)
    return float(np.mean(y_true <= y_pred_quantile))


def quantile_calibration_table(
    y_true: pd.Series, preds: dict[str, pd.Series]
) -> pd.DataFrame:
    rows = []
    targets = {"q80": 0.80, "q90": 0.90, "q95": 0.95}
    for name, target in targets.items():
        if name not in preds:
            continue
        cov = quantile_coverage(y_true, preds[name])
        rows.append(
            {
                "Квантиль": name,
                "Ожидаемое покрытие": f"{target * 100:.0f}%",
                "Фактическое покрытие": f"{cov * 100:.1f}%",
                "Отклонение, п.п.": round((cov - target) * 100, 1),
                "Калибровка": "OK" if abs(cov - target) <= 0.05 else "требует пересмотра",
            }
        )
    return pd.DataFrame(rows)


def wape_robustness(
    df: pd.DataFrame, y_pred_col: str = "pred_q50"
) -> pd.DataFrame:
    """Три варианта расчёта WAPE для оценки чувствительности к стокаутам.

    1. Без дефицитных дней (как сейчас в ВКР);
    2. С дефицитными днями как фактом iiko (нули включены);
    3. С интерполированным спросом (нижняя оценка спроса).
    """
    rows = []

    no_def = df[df["is_deficit"] == 0]
    rows.append(
        {"Сценарий": "Без дефицитных дней", "WAPE, %": wape(no_def["demand_qty"], no_def[y_pred_col])}
    )
    full = df.copy()
    rows.append(
        {"Сценарий": "С дефицитными днями как фактом iiko", "WAPE, %": wape(full["demand_qty"], full[y_pred_col])}
    )
    full_interp = full.copy()
    full_interp.loc[full_interp["is_deficit"] == 1, "demand_qty"] = full_interp.loc[
        full_interp["is_deficit"] == 1, "rolling_mean_7d"
    ]
    rows.append(
        {
            "Сценарий": "С интерполированным спросом (нижняя оценка)",
            "WAPE, %": wape(full_interp["demand_qty"], full_interp[y_pred_col]),
        }
    )
    return pd.DataFrame(rows).round(2)
