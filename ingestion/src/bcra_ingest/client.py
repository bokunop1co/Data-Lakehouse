"""HTTP client for the BCRA "Estadisticas Cambiarias" API (v1.0)."""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import requests

LOG = logging.getLogger(__name__)

BASE_URL = "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones"

# The API answers 403 to the default python-requests User-Agent (verified manually),
# so we send a descriptive one.
HEADERS = {"User-Agent": "data-lakehouse/0.1 (portfolio project)", "Accept": "application/json"}


class BcraClient:
    # Inicializa el cliente HTTP con su configuración de sesión y reintentos.
    def __init__(
        self,
        verify_tls: bool = True,
        max_retries: int = 4,
        backoff_seconds: float = 2.0,
        timeout: int = 30,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # SECURITY: the BCRA host has historically served an incomplete certificate chain,
        # which makes verification fail on some machines. Disabling verification is opt-in
        # (--insecure-skip-tls-verify) and logged loudly. Prefer fixing the CA bundle
        # (e.g. REQUESTS_CA_BUNDLE) instead of using this flag.
        self.session.verify = verify_tls
        if not verify_tls:
            LOG.warning("TLS verification is DISABLED. Do not use this outside local experiments.")

    # Obtiene el JSON crudo de un día, con reintentos ante errores transitorios.
    def get_day(self, day: date) -> dict[str, Any]:
        """Return the raw JSON for one day, retrying on transient errors."""
        params = {"fecha": day.isoformat()}
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(BASE_URL, params=params, timeout=self.timeout)
                # 429 / 5xx are transient; other 4xx are our fault and should fail fast.
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(f"transient status {resp.status_code}", response=resp)
                resp.raise_for_status()
                return resp.json()
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                transient = status is None or status == 429 or status >= 500
                if not transient or attempt == self.max_retries:
                    raise
                delay = self.backoff_seconds * 2 ** (attempt - 1)
                LOG.warning(
                    "%s: %s (attempt %d/%d), retrying in %.0fs",
                    day, exc, attempt, self.max_retries, delay,
                )
                time.sleep(delay)
        raise RuntimeError("unreachable")
