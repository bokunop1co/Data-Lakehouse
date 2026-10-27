import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from bcra_ingest.storage import write_partitioned
from bcra_ingest.transform import COLUMNS, flatten_day

FIXTURES = Path(__file__).parent / "fixtures"
TS = datetime(2025, 10, 2, tzinfo=UTC)


# Carga un archivo JSON de ejemplo usado como fixture.
def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# Verifica la forma y los tipos de columnas del resultado aplanado.
def test_flatten_day_shape_and_types():
    df = flatten_day(load("cotizaciones_2025-10-01.json"), ingested_at=TS)
    assert list(df.columns) == COLUMNS
    assert len(df) == 8
    assert set(df["rate_date"]) == {date(2025, 10, 1)}
    assert df["tipo_cotizacion"].dtype == "float64"
    assert "BRL" in set(df["currency_code"])


# Verifica los valores concretos del resultado aplanado.
def test_flatten_day_values():
    df = flatten_day(load("cotizaciones_2025-10-01.json"), ingested_at=TS)
    brl = df[df["currency_code"] == "BRL"].iloc[0]
    assert brl["tipo_cotizacion"] == 266.83418


# Verifica que un día no hábil devuelve un DataFrame vacío.
def test_non_business_day_returns_empty_frame():
    df = flatten_day(load("cotizaciones_empty.json"))
    assert df.empty
    assert list(df.columns) == COLUMNS


# Verifica que la escritura use el esquema de particiones estilo Hive.
def test_write_partitioned_hive_layout(tmp_path):
    df = flatten_day(load("cotizaciones_2025-10-01.json"), ingested_at=TS)
    files = write_partitioned(df, tmp_path)
    assert [f.relative_to(tmp_path).as_posix() for f in files] == [
        "bcra_fx/dt=2025-10-01/data.parquet"
    ]
    assert len(pd.read_parquet(files[0])) == 8


# Verifica que un DataFrame vacío no genera archivos.
def test_write_partitioned_empty_writes_nothing(tmp_path):
    assert write_partitioned(flatten_day(load("cotizaciones_empty.json")), tmp_path) == []
