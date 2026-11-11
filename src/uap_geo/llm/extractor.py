"""Anthropic Messages API client for feature extraction: synchronous for samples, Message Batches for the
full set. Every call forces the record_features tool so outputs are structured."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable

import pandas as pd

from uap_geo.llm.schema import SCHEMA_VERSION, SYSTEM, TOOL, user_message

log = logging.getLogger(__name__)


class FeatureExtractor:
    def __init__(self, model: str, max_tokens: int = 700, client=None) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY
        return self._client

    def params(self, text: str, duration_s: float | None) -> dict:
        return {
            "model": self.model, "max_tokens": self.max_tokens, "system": SYSTEM, "tools": [TOOL],
            "tool_choice": {"type": "tool", "name": TOOL["name"]},
            "messages": [{"role": "user", "content": user_message(text, duration_s)}],
        }

    @staticmethod
    def _features(message) -> dict | None:
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                return dict(block.input)
        return None

    def _row(self, report_id: str, features: dict | None, error: str | None = None) -> dict:
        return {"report_id": report_id, "schema": SCHEMA_VERSION, "model": self.model,
                "features": json.dumps(features) if features is not None else None, "error": error}

    # ------------------------------------------------------------------------------ synchronous
    def extract(self, rows: pd.DataFrame, retries: int = 3) -> pd.DataFrame:
        out = []
        for i, row in enumerate(rows.itertuples(index=False), start=1):
            for attempt in range(retries):
                try:
                    message = self.client.messages.create(**self.params(row.text, row.duration_s))
                    out.append(self._row(row.report_id, self._features(message)))
                    break
                except Exception as exc:  # retry transient errors, record the last one
                    if attempt == retries - 1:
                        out.append(self._row(row.report_id, None, str(exc)[:300]))
                    else:
                        time.sleep(2 ** attempt)
            if i % 50 == 0:
                log.info("Extracted %d/%d", i, len(rows))
        return pd.DataFrame(out)

    # ------------------------------------------------------------------------------ batches
    def submit(self, rows: pd.DataFrame, chunk: int = 20000) -> list[str]:
        ids = []
        for start in range(0, len(rows), chunk):
            part = rows.iloc[start:start + chunk]
            requests = [{"custom_id": r.report_id, "params": self.params(r.text, r.duration_s)}
                        for r in part.itertuples(index=False)]
            batch = self.client.messages.batches.create(requests=requests)
            log.info("Submitted batch %s with %d requests", batch.id, len(requests))
            ids.append(batch.id)
        return ids

    def status(self, batch_ids: Iterable[str]) -> dict[str, str]:
        return {b: self.client.messages.batches.retrieve(b).processing_status for b in batch_ids}

    def collect(self, batch_ids: Iterable[str]) -> pd.DataFrame:
        out = []
        for b in batch_ids:
            for result in self.client.messages.batches.results(b):
                outcome = result.result
                if outcome.type == "succeeded":
                    out.append(self._row(result.custom_id, self._features(outcome.message)))
                else:
                    out.append(self._row(result.custom_id, None, outcome.type))
        return pd.DataFrame(out)
