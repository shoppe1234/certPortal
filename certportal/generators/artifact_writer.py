"""
Artifact Writer — Writes generated spec artifacts to S3 and updates the DB.

Uses S3AgentWorkspace from certportal.core.workspace (INV-06 compliant)
and asyncpg from certportal.core.database (portal async pattern).

S3 path pattern: {retailer_slug}/specs/{x12_version}/{transaction_code}.{ext}
Example: lowes/specs/004010/850.md

Architecture Decision: AD-9 from wizard refactoring prompt.
Constraint: INV-06 — All paths scoped to {retailer_slug}/.
Constraint: INV-07 — Portals never import from agents/.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from certportal.core.database import get_pool
from certportal.core.workspace import S3AgentWorkspace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# S3 key helpers
# ---------------------------------------------------------------------------

def _artifact_s3_key(
    transaction_type: str,
    x12_version: str,
    ext: str,
) -> str:
    """
    Build the S3 key (relative to retailer scope) for an artifact.

    Returns a key like: specs/004010/850.md
    The S3AgentWorkspace will prepend {retailer_slug}/.
    """
    return f"specs/{x12_version}/{transaction_type}.{ext}"


def _artifacts_s3_prefix(x12_version: str) -> str:
    """
    Build the S3 prefix for all artifacts of a given X12 version.

    Returns: specs/{x12_version}/
    """
    return f"specs/{x12_version}/"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def write_artifacts(
    retailer_slug: str,
    transaction_type: str,
    x12_version: str,
    artifacts: dict[str, bytes],
) -> list[str]:
    """
    Write generated artifacts to S3 using S3AgentWorkspace.

    Args:
        retailer_slug: Retailer identifier (e.g. "lowes").
        transaction_type: X12 transaction set code (e.g. "850").
        x12_version: X12 version (e.g. "004010").
        artifacts: Dict mapping format extension to content bytes.
                   Example: {"md": b"...", "html": b"...", "pdf": b"..."}

    Returns:
        List of full S3 keys that were written.
    """
    workspace = S3AgentWorkspace(retailer_slug=retailer_slug)
    written_keys: list[str] = []

    for ext, content in artifacts.items():
        key = _artifact_s3_key(transaction_type, x12_version, ext)
        try:
            full_key = workspace.upload(key, content)
            written_keys.append(full_key)
            logger.info(
                "Wrote artifact: %s (%d bytes)", full_key, len(content)
            )
        except Exception as exc:
            logger.error(
                "Failed to write artifact %s/%s/%s.%s: %s",
                retailer_slug, x12_version, transaction_type, ext, exc,
            )

    return written_keys


async def update_retailer_specs(
    retailer_slug: str,
    x12_version: str,
    transaction_types: list[str],
    artifacts_s3_prefix: str | None = None,
) -> None:
    """
    Update the retailer_specs DB table with artifact metadata.

    Inserts or updates a row indicating that specs have been generated
    for the given retailer, X12 version, and transaction types.

    Uses asyncpg (portal async pattern).

    Args:
        retailer_slug: Retailer identifier.
        x12_version: X12 version (e.g. "004010").
        transaction_types: List of transaction type codes included.
        artifacts_s3_prefix: S3 prefix where artifacts are stored.
    """
    if artifacts_s3_prefix is None:
        artifacts_s3_prefix = f"{retailer_slug}/{_artifacts_s3_prefix(x12_version)}"

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if a row already exists for this retailer + version
        existing = await conn.fetchrow(
            """
            SELECT id FROM retailer_specs
            WHERE retailer_slug = $1 AND x12_version = $2
            """,
            retailer_slug, x12_version,
        )

        if existing:
            # Update existing row
            await conn.execute(
                """
                UPDATE retailer_specs
                SET transaction_types = $1,
                    artifacts_s3_prefix = $2,
                    layer2_configured = TRUE,
                    created_at = now()
                WHERE retailer_slug = $3 AND x12_version = $4
                """,
                transaction_types,
                artifacts_s3_prefix,
                retailer_slug,
                x12_version,
            )
            logger.info(
                "Updated retailer_specs for %s/%s: %s",
                retailer_slug, x12_version, transaction_types,
            )
        else:
            # Insert new row
            await conn.execute(
                """
                INSERT INTO retailer_specs
                    (retailer_slug, spec_version, thesis_s3_key,
                     x12_version, transaction_types, artifacts_s3_prefix,
                     layer2_configured)
                VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                """,
                retailer_slug,
                f"wizard-{x12_version}",  # spec_version
                artifacts_s3_prefix,       # thesis_s3_key (reuse for prefix)
                x12_version,
                transaction_types,
                artifacts_s3_prefix,
            )
            logger.info(
                "Inserted retailer_specs for %s/%s: %s",
                retailer_slug, x12_version, transaction_types,
            )


async def get_artifact_url(
    retailer_slug: str,
    transaction_type: str,
    x12_version: str,
    ext: str,
) -> str | None:
    """
    Return the S3 key for a specific artifact if it exists.

    Args:
        retailer_slug: Retailer identifier.
        transaction_type: X12 transaction set code.
        x12_version: X12 version.
        ext: File extension ("md", "html", "pdf").

    Returns:
        Full S3 key if the artifact exists, None otherwise.
    """
    workspace = S3AgentWorkspace(retailer_slug=retailer_slug)
    key = _artifact_s3_key(transaction_type, x12_version, ext)

    try:
        if workspace.exists(key):
            return f"{retailer_slug}/{key}"
    except Exception as exc:
        logger.warning(
            "Failed to check artifact existence %s/%s: %s",
            retailer_slug, key, exc,
        )

    return None
