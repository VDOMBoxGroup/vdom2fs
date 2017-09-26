#!/usr/bin/env python

import argparse
import imp
from md5 import md5
import sys

from vdom_remote_api import VDOMServiceSingleThread

def fetch_app(url, user, pass_md5, app_id):
    print "Fetching application: ", url, user, pass_md5, app_id

    try:
        con = VDOMServiceSingleThread.connect(url, user, pass_md5, app_id)
        xml = con.remote("export_application")
        return xml
    except AttributeError, e:
        print "Something failed. Check your credentials"
        return None

def main(argv):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False
    )
    parser.add_argument('-c', '--conf_file',
            help="Specify config file", metavar="FILE", required=True)
    args, remaining_argv = parser.parse_known_args()

    config = imp.load_source('config', args.conf_file)

    xml = fetch_app(config.url, config.user, config.pass_md5, config.app_id)
    if not xml:
        print "ERROR: No data exported"
        return -1

    with open("exported_app.xml", "wb") as f:
        f.write(xml.encode('utf8'))

    

if __name__ == "__main__":
    exit(main(sys.argv))
