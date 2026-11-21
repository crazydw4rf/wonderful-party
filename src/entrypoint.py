import argparse
import sys

from .constants import SUPPORTED_LANGUAGES
from .extractor import extract_all_patches
from .patcher import apply_patches, build_binaries
from .progress import update_progress_and_badges
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

    # progress
    subparsers.add_parser("progress", help="Calculate progress statistics and update Shields.io badges")

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
        build_binaries(args.lang, repatch=args.repatch)

    elif args.command == "progress":
        update_progress_and_badges()


if __name__ == "__main__":
    main()
