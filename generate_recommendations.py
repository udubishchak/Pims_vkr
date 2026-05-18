"""Расчёт рекомендованного объёма заказа на горизонт LT (см. раздел 3.4 ВКР).

Q_рек = Прогноз_LT + SS - Остаток_тек - Ожид_поставки

* Прогноз_LT — сумма квантильных прогнозов q50 на L дней;
* SS — страховой запас как разность квантиля по ABC-группе и q50;
* для скоропортящихся (shelf_open_days <= 3) уровень сервиса снижается на 5 п.п.;
* для shelf_open_days <= 5 применяется newsvendor-коррекция;
* округление вверх до кратного pack_size, при 0 < Q < MOQ → Q := MOQ.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import (
    PERISHABLE_QUANTILE_REDUCTION,
    PERISHABLE_SHELF_DAYS,
    SERVICE_LEVEL_BY_ABC,
)

logger = logging.getLogger("generate_recommendations")


# Карта «целевой квантиль» → «следующий ниже» для скоропортящихся
_QUANTILE_DOWNGRADE = {0.95: 0.90, 0.90: 0.80, 0.80: 0.80}


@dataclass
class OrderRecommendation:
    location_id: int
    product_id: int
    forecast_lt: float
    safety_stock: float
    stock_open: float
    in_transit: float
    q_raw: float
    q_recommended: float
    rationale: str


def _pick_quantile_column(abc: str, shelf_open_days: float) -> tuple[str, float]:
    base = SERVICE_LEVEL_BY_ABC.get(abc, 0.80)
    if shelf_open_days <= PERISHABLE_SHELF_DAYS:
        base = _QUANTILE_DOWNGRADE.get(base, base - PERISHABLE_QUANTILE_REDUCTION)
    name_map = {0.95: "pred_q95", 0.90: "pred_q90", 0.80: "pred_q80"}
    return name_map[base], base


def _round_to_pack(q: float, pack_size: float, moq: float) -> float:
    if q <= 0:
        return 0.0
    if q < moq:
        return float(moq)
    return float(np.ceil(q / pack_size) * pack_size)


def newsvendor_adjust(
    row: pd.Series, q_calc: float, lead_time: int
) -> tuple[float, str]:
    """Три случая (раздел 3.4.2 ВКР)."""
    stock_open = float(row.get("stock_open", 0.0))
    forecast_lt = float(row["forecast_lt"])
    days_to_expiry = float(row.get("days_to_expiry", 999))
    shelf_open_days = float(row.get("shelf_open_days", 999))

    if shelf_open_days <= 5 and stock_open * 0.8 >= forecast_lt and days_to_expiry > lead_time:
        return 0.0, "избыточный остаток — риск списания"
    if shelf_open_days <= 5 and days_to_expiry <= lead_time:
        return forecast_lt + float(row["safety_stock"]), "истекающая партия: остаток не вычитается"
    if shelf_open_days <= 3:
        cap = float(row.get("forecast_3d", forecast_lt)) * 1.2
        return min(q_calc, cap), "ограничение для скоропортящихся: не более 3-дневного прогноза × 1.2"
    return q_calc, "стандартный расчёт"


def compute_recommendations(
    predictions: pd.DataFrame,
    products: pd.DataFrame,
    stock: pd.DataFrame,
    lead_time: int = 1,
) -> pd.DataFrame:
    df = predictions.merge(
        products[["product_id", "abc_group", "shelf_open_days", "moq", "pack_size", "channel"]],
        on="product_id",
        how="left",
    ).merge(
        stock[["location_id", "product_id", "date", "stock_open", "in_transit", "days_to_expiry"]],
        on=["location_id", "product_id", "date"],
        how="left",
    )

    rows = []
    for (loc, pid), g in df.groupby(["location_id", "product_id"]):
        g = g.sort_values("date").head(lead_time)
        abc = g["abc_group"].iloc[0]
        shelf = float(g["shelf_open_days"].iloc[0])
        q_col, _ = _pick_quantile_column(abc, shelf)
        forecast_lt = g["pred_q50"].sum()
        safety_stock = (g[q_col] - g["pred_q50"]).clip(lower=0).sum()

        stock_open = float(g["stock_open"].iloc[0])
        in_transit = float(g["in_transit"].iloc[0])
        days_to_expiry = float(g["days_to_expiry"].iloc[0])

        q_raw = max(0.0, forecast_lt + safety_stock - stock_open - in_transit)
        row = {
            "stock_open": stock_open,
            "forecast_lt": forecast_lt,
            "forecast_3d": g["pred_q50"].head(3).sum(),
            "safety_stock": safety_stock,
            "shelf_open_days": shelf,
            "days_to_expiry": days_to_expiry,
        }
        q_adjusted, rationale = newsvendor_adjust(pd.Series(row), q_raw, lead_time)
        q_final = _round_to_pack(
            q_adjusted, float(g["pack_size"].iloc[0]), float(g["moq"].iloc[0])
        )
        rows.append(OrderRecommendation(
            location_id=loc, product_id=pid,
            forecast_lt=forecast_lt, safety_stock=safety_stock,
            stock_open=stock_open, in_transit=in_transit,
            q_raw=q_raw, q_recommended=q_final, rationale=rationale,
        ).__dict__)
    return pd.DataFrame(rows)
