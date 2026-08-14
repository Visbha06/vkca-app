"""Bounded background-job operator command entry point."""

import argparse


def main() -> None:
    """Expose planned command names while Phase 1 is being assembled."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("status", "dispatch", "recover", "retry", "trigger-rag"),
    )
    parser.parse_args()
    raise SystemExit(
        "Background-job commands are not available until the processing "
        "foundation is implemented."
    )


if __name__ == "__main__":
    main()
