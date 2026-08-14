"""Dedicated background worker entry point."""


def main() -> None:
    """Fail clearly until the Phase 2 worker runtime is installed."""

    raise SystemExit(
        "Background worker runtime is not available until Phase 2 is implemented."
    )


if __name__ == "__main__":
    main()
