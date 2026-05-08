from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = Path(__file__).resolve().parent / "reports"


def build_command(verbose: bool, max_fail: int, with_report: bool) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        f"--maxfail={max_fail}",
    ]

    if not verbose:
        command.append("-q")

    if with_report:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        command.extend(["--junitxml", str(REPORT_DIR / "latest-regression.xml")])

    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run regression tests for Defender Ops Learning Lab.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose pytest output.")
    parser.add_argument(
        "--maxfail",
        type=int,
        default=1,
        help="Stop after this many failures (default: 1).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Write JUnit XML report to continuous_validation/reports/latest-regression.xml.",
    )
    args = parser.parse_args()

    command = build_command(verbose=args.verbose, max_fail=max(1, args.maxfail), with_report=args.report)
    print("Running regression suite:", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)

    if args.report:
        print("JUnit report:", REPORT_DIR / "latest-regression.xml")

    if result.returncode == 0:
        print("Regression status: PASS")
    else:
        print("Regression status: FAIL")

    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
