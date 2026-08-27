#!/usr/bin/env python3
"""فحص عقود الأحداث الأساسية من المانيفستات، بلا تخمين وبلا نشر بيانات."""
from __future__ import annotations

import sys

from collections import defaultdict
from pathlib import Path
import ast

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from build_registry.paths import RegistryAtomRoot
ATOMS = RegistryAtomRoot(ROOT)

# هذه مصادر خارجية اختيارية. غياب ناشرها ليس انقطاعًا في مسار BTCUSD الحالي.
INTENTIONALLY_UNUSED_EVENTS = {
    "SYS_15MIN": "UNUSED_EVENT",
}

OPTIONAL_EXTERNAL_INPUTS = {
    "market.trade",
    # Explicit owner/operator command; no autonomous publisher is allowed.
    "asset.extraction.retry_requested",
    "feed.binance.tick",
    "feed.yahoo.tick",
    "feed.rithmic.tick",
    # External clock/replay inputs are optional surfaces in this release.
    # Their absence is reported, but it is not a broken internal edge.
    "SYS_10MS",
    "replay.session.start",
    "replay.session.stop",
}

# الرابط هنا مقصود ومثبت: (الحدث، الناشرون المطلوبون، المستمعون المطلوبون).
REQUIRED_LINKS = {
    "feed.ctrader.tick": ({622}, {521, 582, 613}),
    # 580 intentionally consumes only decision.gate.passed after owner approval;
    # requiring the pre-gate score here contradicted its sealed safety contract.
    "decision.scored.state": ({453}, {360, 450, 458}),
    "market.tick": ({613}, {112, 115}),
    "market.tick.validated": ({112}, {102, 103, 105}),
    # البند ٤ (حكم المالك): 467 توقّف عن نشر طلب التنفيذ وصار طبقة تشخيص تنشر
    # `decision.dispatch.state`؛ المنتِج هو مسار 581 وحده (576 البداية · 578 الفروق).
    "execution.order.requested": ({576, 578}, {578, 586, 707}),
    "decision.dispatch.state": ({467}, {707}),
    "symbol.resolve.requested": ({586}, {708}),
    "symbol.resolve.result": ({708}, {586}),
    "execution.order.resolved": ({586}, {585}),
    "risk.margin.validation.completed": ({585}, {516}),
    "execution.order.built": ({551}, {550, 584, 703, 707}),
    "execution.order.legal": ({584}, {552}),
    "execution.command.ack": ({563, 601}, {520, 550, 570, 578}),
    "platform.brain_signal.written": ({601}, {522, 550, 704}),
    "symbol.resolve.orphaned": ({586}, {704}),
    "execution.reference_divergence.state": ({582}, {578}),
    "execution.snapshot.state": ({583}, {578}),
    "asset.extraction.failed": ({579}, {524}),
    "risk.exposure.state": ({508}, {500, 552}),
    "learning.model.selected": ({366}, {367}),
    "model.persist_requested": ({367}, {706}),
    "model.persisted": ({706}, {367}),
    "portfolio.components.state": ({650}, {662, 668}),
}


def main() -> int:
    publishers: dict[str, set[int]] = defaultdict(set)
    subscribers: dict[str, set[int]] = defaultdict(set)
    problems: list[str] = []
    syntax_errors: list[str] = []

    for manifest in sorted(ATOMS.rglob("manifest.yaml")):
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            atom_id = int(data["id"])
            for event in data.get("publishes", []) or []:
                publishers[str(event)].add(atom_id)
            for event in data.get("subscribes", []) or []:
                subscribers[str(event)].add(atom_id)
            ast.parse((manifest.parent / "atom.py").read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            syntax_errors.append(f"{manifest.relative_to(ROOT)} — {exc}")

    for event, (wanted_publishers, wanted_subscribers) in REQUIRED_LINKS.items():
        actual_p = publishers.get(event, set())
        actual_s = subscribers.get(event, set())
        missing_p = wanted_publishers - actual_p
        missing_s = wanted_subscribers - actual_s
        if missing_p:
            problems.append(f"{event}: ناشرون ناقصون {sorted(missing_p)}")
        if missing_s:
            problems.append(f"{event}: مستمعون ناقصون {sorted(missing_s)}")

    for event, classification in INTENTIONALLY_UNUSED_EVENTS.items():
        if not publishers.get(event):
            problems.append(f"{event}: {classification} بلا ناشر")
        if subscribers.get(event):
            problems.append(f"{event}: مُصنّف {classification} لكن له مستمعون {sorted(subscribers[event])}")

    no_publisher = sorted(event for event in subscribers if not publishers[event])
    unexpected_no_publisher = [
        event for event in no_publisher if event not in OPTIONAL_EXTERNAL_INPUTS
    ]
    if unexpected_no_publisher:
        problems.append("أحداث لها مستمع بلا ناشر: " + ", ".join(unexpected_no_publisher))

    print("فحص أحداث المشروع")
    print(f"الأحداث المنشورة: {len(publishers)}")
    print(f"الأحداث المسموعة: {len(subscribers)}")
    print("الروابط الأساسية المفحوصة: %d" % len(REQUIRED_LINKS))
    print("الأحداث غير المستخدمة بقرار صريح: %s" % ", ".join(
        f"{event}={classification}" for event, classification in INTENTIONALLY_UNUSED_EVENTS.items()))
    print("مصادر خارجية اختيارية بلا ناشر: %s" % (", ".join(no_publisher) if no_publisher else "لا شيء"))
    print("مخرجات بلا مستمع: %d — هذه مخرجات عرض/سجل وليست انقطاعًا" % sum(
        1 for event in publishers if not subscribers[event]
    ))
    if syntax_errors:
        problems.extend("كود ذرة غير قابل للتحليل: " + item for item in syntax_errors)

    if problems:
        for problem in problems:
            print("❌ " + problem)
        return 1
    print("✅ الأحداث الأساسية موصولة؛ المصادر الخارجية غير المتاحة معلّمة اختيارية فقط.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
