#!/usr/local/bin/python
# encoding: utf-8

import sys

if sys.version_info < (2, 7):
    raise Exception("must use python 2.7 or greater")

import argparse
import vdom_builder


def main():
    """Main function
    """
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument(
        "src",
        help="path to source folder",
        type=str
    )
    args_parser.add_argument(
        "dst",
        help="path to destination XML file",
        type=str
    )
    args_parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true",
        default=False,
    )
    args_parser.add_argument(
        "-l",
        "--library",
        help="path to library folder",
        type=str,
    )
    args_parser.add_argument(
        "-lcm",
        "--library-copy-mode",
        help=("library cope mode: instead - use passed "
              "foler instead of existing, replace - replace "
              "existing files with new"),
        choices=("instead", "replace"),
        default="instead",
        type=str,
    )

    args = args_parser.parse_args()

    vdom_bl = vdom_builder.create()

    vdom_bl.src = args.src
    vdom_bl.dst = args.dst
    vdom_bl.debug = args.verbose
    vdom_bl.library = args.library
    vdom_bl.library_copy_mode = args.library_copy_mode

    vdom_bl.start()


if __name__ == "__main__":
    main()
    sys.exit(0)
