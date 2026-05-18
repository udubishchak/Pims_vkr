"""Глобальная конфигурация прототипа PIMS.
"""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"

# Признаки модели (см. таблицу 3.3 ВКР, 23 признака)
FEATURE_COLS = [
    "lag_1", "lag_2", "lag_3", "lag_7", "lag_14", "lag_28",
    "roll_mean_7", "roll_mean_14", "roll_std_7", "roll_std_14",
    "temperature_c", "humidity_pct", "precipitation_mm", "is_rainy",
    "day_of_week", "month", "week_of_year",
    "is_weekend", "is_friday", "is_saturday",
    "is_holiday", "is_promo", "discount_pct",
]
TARGET_COL = "demand_qty"

# Квантили (см. раздел 3.4.1)
QUANTILES = {"q50": 0.50, "q80": 0.80, "q90": 0.90, "q95": 0.95}

# Базовые гиперпараметры LightGBM (см. раздел 3.3.2)
LGBM_PARAMS = dict(
    n_estimators=400,
    learning_rate=0.05,
    max_depth=7,
    num_leaves=31,
    min_child_samples=20,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=0.1,
    random_state=42,
    verbosity=-1,
)

# Правило обнаружения дефицитных дней (раздел 2.4.4)
DEFICIT_STOCK_RATIO_THRESHOLD = 0.15
DEFICIT_DEMAND_DROP_THRESHOLD = 0.50

# Уровни сервиса по ABC-группам (раздел 3.4.1)
SERVICE_LEVEL_BY_ABC = {"A": 0.95, "B": 0.90, "C": 0.80}

# Дополнительное снижение для скоропортящихся (shelf_open_days <= 3)
PERISHABLE_SHELF_DAYS = 3
PERISHABLE_QUANTILE_REDUCTION = 0.05  # 5 п.п.
