"""Deployment-network preflight for externally previewable services.

This module does not open ports or manage the runtime. It validates the
configuration that the launchers are about to use and fails closed when a
publicly bound Core API has no credential configured.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required for network preflight") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid core config: {path}")
    return data


def _is_public_host(host: str) -> bool:
    return host in {"0.0.0.0", "::", "::0"} or host not in {"127.0.0.1", "localhost", "::1"}


def _api_key_present() -> bool:
    return bool(
        os.environ.get("QUANT_CORE_API_KEY")
        or os.environ.get("QUANT_GOV_API_KEY")
    )


def validate_config(path: Path, expected_port: int) -> dict[str, Any]:
    data = _config(path)
    api = data.get("api") or {}
    if not bool(api.get("enable_api", True)):
        raise RuntimeError(f"API disabled in {path}")
    host = str(api.get("host", "")).strip()
    port = int(api.get("port", -1))
    if host != "0.0.0.0":
        raise RuntimeError(
            f"{path}: public preview requires api.host=0.0.0.0; found {host!r}"
        )
    if port != expected_port:
        raise RuntimeError(
            f"{path}: expected api.port={expected_port}; found {port}"
        )
    if not _api_key_present():
        raise RuntimeError(
            f"{path}: public API binding requires QUANT_GOV_API_KEY or QUANT_CORE_API_KEY"
        )
    return {"host": host, "port": port}


def validate_market(market: str) -> dict[str, Any]:
    market = str(market).strip().lower()
    if market == "forex":
        return validate_config(PROJECT_ROOT / "config" / "core_forex.yaml", 8010)
    if market == "crypto":
        return validate_config(PROJECT_ROOT / "config" / "core_crypto.yaml", 8020)
    raise ValueError(f"unknown market: {market}")


def validate_all() -> dict[str, dict[str, Any]]:
    return {
        "forex": validate_market("forex"),
        "crypto": validate_market("crypto"),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate QUANT_NQ network exposure before startup")
    parser.add_argument("--market", choices=("forex", "crypto", "all"), default="all")
    args = parser.parse_args()

    try:
        result = validate_all() if args.market == "all" else {args.market: validate_market(args.market)}
    except Exception as exc:  # noqa: BLE001
        print(f"NETWORK PREFLIGHT: FAIL — {exc}")
        return 2

    for market, cfg in result.items():
        print(
            f"NETWORK PREFLIGHT: PASS — {market} API {cfg['host']}:{cfg['port']} "
            "authentication=environment"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
