"""Pure functions: raw BCRA payload -> flat DataFrame. No I/O, easy to unit test."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

COLUMNS = [
    "rate_date",
    "currency_code",
    "currency_name",
    "tipo_pase",
    "tipo_cotizacion",
    "ingested_at",
]


# Aplana la respuesta diaria de la API en un DataFrame con una fila por detalle.
def flatten_day(payload: dict[str, Any], ingested_at: datetime | None = None) -> pd.DataFrame:
    """Flatten one day's response (results.fecha + results.detalle[]) into rows.

    Non-business days come back as {"fecha": null, "detalle": []} -> empty frame.
    """
    results = payload.get("results") or {}
    detail = results.get("detalle") or []
    fecha = results.get("fecha")
    if not fecha or not detail:
        return pd.DataFrame(columns=COLUMNS)

    ts = ingested_at or datetime.now(UTC)
    rows = [
        {
            "rate_date": fecha,
            "currency_code": item["codigoMoneda"],
            "currency_name": item.get("descripcion"),
            "tipo_pase": item.get("tipoPase"),
            "tipo_cotizacion": item.get("tipoCotizacion"),
            "ingested_at": ts,
        }
        for item in detail
    ]
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["rate_date"] = pd.to_datetime(df["rate_date"]).dt.date
    df["tipo_pase"] = df["tipo_pase"].astype("float64")
    df["tipo_cotizacion"] = df["tipo_cotizacion"].astype("float64")
    return df
