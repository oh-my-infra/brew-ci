#!/usr/bin/env python3
"""Validate the canonical brew-ci calendar version contract."""

from __future__ import annotations

import argparse
import datetime as dt
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CALVER = re.compile(
    r"^(?P<year>\d{4})\.(?P<month>\d{2})\.(?P<day>\d{2})\."
    r"(?P<revision>[1-9]\d*)$"
)


def parse_calver(value: str) -> tuple[dt.date, int]:
    match = CALVER.fullmatch(value)
    if not match:
        raise ValueError("version must use YYYY.MM.DD.N with a non-zero-padded positive N")

    try:
        release_date = dt.date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError as error:
        raise ValueError(f"version contains an invalid calendar date: {error}") from error

    return release_date, int(match.group("revision"))


def current_date(timezone: str) -> dt.date:
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown timezone: {timezone}") from error
    return dt.datetime.now(zone).date()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--tag", help="optional Git tag to compare with the version")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument(
        "--require-today",
        action="store_true",
        help="require the CalVer date to equal today in --timezone",
    )
    parser.add_argument(
        "--today",
        type=dt.date.fromisoformat,
        help="test override for today's date; implies --require-today",
    )
    args = parser.parse_args()

    release_date, _ = parse_calver(args.version)

    if args.tag is not None and args.tag != f"v{args.version}":
        raise SystemExit(f"tag {args.tag!r} does not match version v{args.version}")

    if args.require_today or args.today is not None:
        today = args.today or current_date(args.timezone)
        if release_date != today:
            raise SystemExit(
                f"version date {release_date.isoformat()} does not match release date "
                f"{today.isoformat()} in {args.timezone}"
            )

    print(args.version)


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error)) from error
