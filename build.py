#!/usr/bin/python
#encoding: utf-8

import os
import sys

import vdom_builder

############## MAIN FUNCTIONS ##############

def print_help():
    """Print help Information
    """

    print " usage: parse.py source_folder [dst]\n\tdst - destination XML file name\n\n"


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

    print "\nVDOM Application XML builder (v. {version})\n".format(version=vdom_builder.__version__)

    if len(sys.argv) == 1:
        print_help()

    else:
        args = parse_args()

        builder = vdom_builder.create()

        if args["debug"]: 
            builder.debug = True
        
        if args["dst"]: 
            builder.dst = args["dst"]

        builder.src = args["src"]
        builder.start()

    sys.exit(0)

if __name__ == "__main__":
    main()
