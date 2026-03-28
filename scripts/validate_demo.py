"""End-to-end validation script for SoundSense backend.

Run with:
    PYTHONPATH=. python scripts/validate_demo.py

The backend must be running at http://localhost:8000 before executing this script.
"""

import asyncio
import sys

import httpx

BASE_URL = "http://localhost:8000/api/v1"

SCENARIO_CHECKS = [
    ("someone_enters",  "ARRIVAL_DETECTED"),
    ("alarm_escalation", "ALARM_ESCALATING"),
    ("child_alert",     "CHILD_DISTRESS"),
]


async def main() -> None:
    results: list[tuple[str, bool, str]] = []  # (label, passed, detail)

    async with httpx.AsyncClient(timeout=180.0) as client:

        # ── 1. Health check ───────────────────────────────────────────────────
        try:
            r = await client.get(f"{BASE_URL}/health")
            ok = r.status_code == 200 and r.json().get("status") == "ok"
        except Exception as exc:
            ok = False
            print(f"  [!] Health check error: {exc}")
        results.append(("Health check", ok, "status=ok" if ok else "FAILED — is the server running?"))

        # ── 2. Scenario list ──────────────────────────────────────────────────
        try:
            r = await client.get(f"{BASE_URL}/scenario/list")
            scenarios = r.json().get("scenarios", [])
            names = {s["name"] for s in scenarios}
            expected = {"someone_enters", "alarm_escalation", "water_forgotten",
                        "quiet_background", "child_alert", "glass_break"}
            ok = expected == names
        except Exception as exc:
            ok = False
            print(f"  [!] Scenario list error: {exc}")
        results.append(("Scenario list", ok, f"found {len(names)} scenarios" if ok else f"missing: {expected - names}"))

        # ── 3–5. Full scenario runs ───────────────────────────────────────────
        for scenario_name, expected_flag in SCENARIO_CHECKS:
            label = scenario_name
            try:
                r = await client.post(
                    f"{BASE_URL}/demo/run",
                    json={"scenario": scenario_name, "wait_for_completion": True},
                )
                data = r.json()
                assert data.get("ok") is True, f"ok=false: {data}"
                assert data.get("peak_flag") == expected_flag, (
                    f"expected {expected_flag}, got {data.get('peak_flag')}"
                )
                assert _URGENCY_RANK.get(data.get("peak_urgency", "low"), 0) > 0, (
                    f"urgency should not be low, got {data.get('peak_urgency')}"
                )
                assert data.get("total_events", 0) > 0, "total_events=0"
                assert data.get("final_explanation"), "final_explanation is empty"

                peak = data["peak_flag"]
                urgency = data["peak_urgency"]
                detail = f"{peak} ({urgency})"
                ok = True
            except AssertionError as exc:
                ok = False
                detail = f"FAILED — {exc}"
            except Exception as exc:
                ok = False
                detail = f"ERROR — {exc}"

            results.append((label, ok, detail))

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)

    print()
    print("SoundSense Demo Validation")
    print("==========================")
    for label, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {label:<20} {status} — {detail}")
    print("==========================")
    print(f"  {passed}/{total} checks passed.", "Ready for demo." if passed == total else "Fix failures above.")
    print()

    sys.exit(0 if passed == total else 1)


_URGENCY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

if __name__ == "__main__":
    asyncio.run(main())
