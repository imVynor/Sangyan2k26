"""Scheduler and refresh coordinator for SANGYAN knowledge sources."""

from datetime import datetime, timezone
from ai.app.sources.change_detector import ChangeDetector
from ai.app.sources.models import SourceCheckResult, SourceCheckStatus, SourceRegistryEntry
from ai.app.sources.registry import SourceRegistry


class SourceScheduler:
    """Coordinates periodic change detection cycles across registered authoritative sources."""

    def __init__(
        self,
        registry: SourceRegistry | None = None,
        detector: ChangeDetector | None = None,
    ) -> None:
        self.registry = registry or SourceRegistry()
        self.detector = detector or ChangeDetector(registry=self.registry)

    async def run_refresh_cycle(
        self,
        active_only: bool = True,
        dry_run: bool = False,
    ) -> list[SourceCheckResult]:
        """Execute a refresh sweep across all eligible registered sources."""
        sources = self.registry.list_sources(active_only=active_only)
        results: list[SourceCheckResult] = []

        now = datetime.now(timezone.utc)
        for src in sources:
            if dry_run:
                results.append(
                    SourceCheckResult(
                        source_id=src.source_id,
                        checked_at=now,
                        status=SourceCheckStatus.UNCHANGED,
                        previous_hash=src.last_content_hash,
                        new_hash=src.last_content_hash,
                    )
                )
                continue

            result = await self.detector.check_source(src)
            results.append(result)

        return results
