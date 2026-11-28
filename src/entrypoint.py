import argparse
import sys

from .constants import SUPPORTED_LANGUAGES
from .extractor import extract_all_patches
from .patcher import apply_patches, build_binaries
from .progress import update_progress_and_badges
from .scenario_list import show_scenario_progress
from .utils import ensure_workspace_setup
from .validator import validate_all


def main():
    parser = argparse.ArgumentParser(
        description="Wonderful Party Translation CLI - Patch and Progress Tools",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # setup
    subparsers.add_parser("setup", help="Bootstrap workspace tools and extract game binaries")

    # extract
    extract_parser = subparsers.add_parser("extract", help="Extract/sync patch templates from scenario data")
    extract_parser.add_argument("lang", choices=list(SUPPORTED_LANGUAGES.keys()), help="Target language code")

    # validate
    val_parser = subparsers.add_parser("validate", help="Validate patch syntax, schema, and original text integrity")
    val_parser.add_argument("lang", nargs="?", choices=list(SUPPORTED_LANGUAGES.keys()), help="Language to validate")

    # apply
    apply_parser = subparsers.add_parser("apply", help="Apply patch files to staging workspace")
    apply_parser.add_argument("lang", choices=list(SUPPORTED_LANGUAGES.keys()), help="Target language code")

    # build
    build_parser = subparsers.add_parser("build", help="Build patched binaries (and optional rePatch zip)")
    build_parser.add_argument("lang", choices=list(SUPPORTED_LANGUAGES.keys()), help="Target language code")
    build_parser.add_argument("--repatch", action="store_true", help="Generate rePatch mod zip for PS Vita")
    build_parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=None,
        help="Max concurrent scenario compile workers (default: auto up to 5)",
    )

    # progress
    subparsers.add_parser("progress", help="Calculate progress statistics and update Shields.io badges")

    # list
    list_parser = subparsers.add_parser(
        "list",
        aliases=["status"],
        help="List per-scenario translation progress with TUI/pager",
    )
    list_parser.add_argument(
        "lang",
        nargs="?",
        choices=list(SUPPORTED_LANGUAGES.keys()),
        help="Target language code (en or id). If omitted, displays both languages.",
    )
    list_parser.add_argument(
        "-s", "--search",
        default="",
        help="Filter scenarios by name, route, or keyword",
    )
    list_parser.add_argument(
        "--sort",
        choices=["name", "progress-desc", "progress-asc", "lines-desc"],
        default="name",
        help="Sort ordering (default: name)",
    )
    list_parser.add_argument(
        "--pager",
        action="store_true",
        help="Force display in system pager (less)",
    )
    list_parser.add_argument(
        "--plain",
        action="store_true",
        help="Force direct plain output without TUI or pager",
    )
    list_parser.add_argument(
        "--tui",
        action="store_true",
        help="Force interactive curses TUI mode",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "setup":
        ensure_workspace_setup()

    elif args.command == "extract":
        extract_all_patches(args.lang)

    elif args.command == "validate":
        success = validate_all(args.lang)
        if not success:
            sys.exit(1)

    elif args.command == "apply":
        apply_patches(args.lang)

    elif args.command == "build":
        build_binaries(args.lang, repatch=args.repatch, jobs=args.jobs)

    elif args.command == "progress":
        update_progress_and_badges()

    elif args.command in ("list", "status"):
        if args.plain:
            mode = "plain"
        elif args.pager:
            mode = "pager"
        elif args.tui:
            mode = "tui"
        else:
            mode = "auto"

        show_scenario_progress(
            lang=args.lang,
            search=args.search,
            sort=args.sort,
            mode=mode,
        )


if __name__ == "__main__":
    main()
