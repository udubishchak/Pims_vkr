"""Веб-сервис уведомления о дедлайне 20:00 (см. раздел 3.4.4 ВКР).

Сервис на FastAPI принимает запрос check_deadline от Airflow DAG-3 в 19:30 МСК;
если в order_actual_log нет записи об отправленном заказе — формирует событие
для плагина iiko Front на кассе менеджера.
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("notifier")
app = FastAPI(title="PIMS notifier", version="1.0")


class DeadlineCheckRequest(BaseModel):
    location_id: int
    deadline_local: time = time(20, 0)


class DeadlineAlert(BaseModel):
    location_id: int
    channel: int
    pending_order: bool
    message: str
    recommendations_url: str


def _has_order_today(location_id: int, channel: int) -> bool:
    """Заглушка: в проде делается SELECT из order_actual_log по сегодняшней дате."""
    return False


@app.post("/check_deadline", response_model=list[DeadlineAlert])
def check_deadline(req: DeadlineCheckRequest) -> list[DeadlineAlert]:
    alerts: list[DeadlineAlert] = []
    for channel in (1, 2):
        if _has_order_today(req.location_id, channel):
            continue
        alerts.append(
            DeadlineAlert(
                location_id=req.location_id,
                channel=channel,
                pending_order=True,
                message=(
                    "Внимание! Дедлайн 20:00 через 30 минут. "
                    f"Заказ по каналу {channel} не отправлен."
                ),
                recommendations_url=(
                    f"https://datalens.yandex.cloud/pims/recs?loc={req.location_id}"
                ),
            )
        )
    return alerts


@app.post("/order_sent")
def order_sent(location_id: int, channel: int, actual_qty: Optional[float] = None) -> dict:
    """Вызывается плагином iiko Front после нажатия 'Заказ отправлен'."""
    logger.info("order_sent: loc=%s ch=%s qty=%s", location_id, channel, actual_qty)
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
