"""Parquet writing (hive-partitioned by dt) and GCS upload."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOG = logging.getLogger(__name__)

PREFIX = "bcra_fx"  # folder inside the bronze bucket


# Escribe el DataFrame en Parquet particionado por fecha (dt) y devuelve los archivos.
def write_partitioned(df: pd.DataFrame, root: Path) -> list[Path]:
    """Write df to root/bcra_fx/dt=YYYY-MM-DD/data.parquet and return the files written.

    One fixed file name per partition, so re-running a day overwrites it (idempotent).
    """
    written: list[Path] = []
    if df.empty:
        return written
    for day, part in df.groupby("rate_date"):
        folder = root / PREFIX / f"dt={day.isoformat()}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "data.parquet"
        # dt lives in the folder name (hive style); BigQuery derives it as a partition column.
        part.to_parquet(path, index=False, engine="pyarrow")
        written.append(path)
    return written


# Sube los archivos Parquet al bucket de GCS conservando la ruta relativa.
def upload_to_gcs(files: list[Path], root: Path, bucket_name: str) -> None:
    from google.cloud import storage  # imported lazily so --dry-run needs no GCP setup

    bucket = storage.Client().bucket(bucket_name)
    for path in files:
        blob_name = path.relative_to(root).as_posix()
        bucket.blob(blob_name).upload_from_filename(str(path))
        LOG.info("uploaded gs://%s/%s", bucket_name, blob_name)
