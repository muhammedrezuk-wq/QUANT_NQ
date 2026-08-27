from __future__ import annotations

import asyncio
from pathlib import Path

from core.bootloader import Bootloader
from core.event_bus import EventBus
from core.journal import Journal
from core.metrics import Metrics
from core.registry import Registry
from tests.core.conftest import write_atom


def test_bootloader_can_load_two_generic_phases_without_duplicate_clock_subscription(tmp_path: Path) -> None:
    atoms = tmp_path / "atoms"
    atoms.mkdir()
    write_atom(atoms, 1)
    write_atom(atoms, 2)
    bus = EventBus()
    registry = Registry()
    loader = Bootloader(atoms, registry, bus, Journal(), Metrics())

    async def scenario() -> None:
        first = await loader.boot(include_ids={1})
        assert first.booted == [1]
        assert registry.find(1) is not None
        assert registry.find(2) is None
        second = await loader.boot(include_ids={2})
        assert second.booted == [2]
        assert registry.find(2) is not None

    asyncio.run(scenario())
    assert bus.subscriber_count("time.utc.synced") == 1
