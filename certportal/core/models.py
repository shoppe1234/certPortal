"""certportal/core/models.py — Shared Pydantic models.

Imported by both agents/ and portals/. Must never import from agents/ or portals/.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ValidationError(BaseModel):
    code: str
    segment: str
    element: str | None = None
    message: str
    severity: Literal["ERROR", "WARNING"]


class ValidationResult(BaseModel):
    supplier_slug: str
    retailer_slug: str
    transaction_type: str
    channel: str
    status: Literal["PASS", "FAIL", "PARTIAL"]
    errors: list[ValidationError]
    passed_at: datetime | None = None
    validated_by: str = "moses"


class PatchSuggestion(BaseModel):
    error_code: str
    segment: str
    element: str | None = None
    summary: str
    patch_s3_key: str
    applied: bool = False
    created_by: str = "ryan"


class HITLGateStatus(BaseModel):
    supplier_id: str
    gate_1: Literal["PENDING", "COMPLETE"] = "PENDING"
    gate_2: Literal["PENDING", "COMPLETE"] = "PENDING"
    gate_3: Literal["PENDING", "COMPLETE", "CERTIFIED"] = "PENDING"
    last_updated: datetime
    last_updated_by: str


class MonicaLogEntry(BaseModel):
    timestamp: datetime
    agent: str
    direction: Literal["Q", "A"]
    message: str
    retailer_slug: str | None = None
    supplier_slug: str | None = None
