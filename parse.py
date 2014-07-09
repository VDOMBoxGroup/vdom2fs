#!/usr/bin/python
#encoding: utf-8

import os
import sys
import xml.parsers.expat

import vdom_parser

############## MAIN FUNCTIONS ##############

def print_help():
    """Print help Information
    """

    print " usage: parse.py source_file [dst]\n\tdst - destination folder\n\n"


def parse_args():
    """Parse CLI args
    """

    return {
        "src": sys.argv[1],
        "dst": sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-d" else "",
        "debug": "-d" in sys.argv[1:]
    }


def main():
    """Main function
    """

    print "\nVDOM Application XML parser (v. {version})\n".format(version=vdom_parser.__version__)

    if len(sys.argv) == 1:
        print_help()

    else:
        args = parse_args()

        parser = vdom_parser.create()

        if args["debug"]: 
            parser.debug = True
        
        if args["dst"]: 
            parser.dst = args["dst"]

        parser.src = args["src"]
        parser.start()

    sys.exit(0)

if __name__ == "__main__":
    main()
