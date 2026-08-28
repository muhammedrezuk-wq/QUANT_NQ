from __future__ import annotations

import sys

from pathlib import Path

from core.manifest_loader import scan

ROOT = Path(__file__).resolve().parents[1]
from build_registry.paths import RegistryAtomRoot
ATOM_ROOT = RegistryAtomRoot(ROOT)
CRYPTO_ROOT = RegistryAtomRoot(ROOT, scope="crypto")



def test_complete_release_contains_forex_and_full_crypto_source() -> None:
    forex = scan(ATOM_ROOT)
    crypto = scan(CRYPTO_ROOT)
    assert not forex.failures, forex.failures
    assert not crypto.failures, crypto.failures
    assert len(forex.atoms) == 233
    assert len(crypto.atoms) == 77  # 2026-08-28: دمج الشريك أدخل 2622 (Binance)
    assert {1001, 1002}.issubset({a.manifest.id for a in crypto.atoms})
    assert len({a.manifest.id for a in crypto.atoms}) == 77  # 2026-08-28: مع 2622


def test_all_packaged_crypto_atoms_have_namespace_above_1000() -> None:
    for path in (CRYPTO_ROOT).iterdir():
        if path.is_dir():
            assert int(path.name.split("_", 1)[0]) >= 1000
