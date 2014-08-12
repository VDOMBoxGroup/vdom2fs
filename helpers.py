#!/usr/bin/env python
# encoding: utf-8

import json
import logging
import os
import re
import shutil
import sys

from uuid import uuid4

from logging import debug as DEBUG, \
    info as INFO, \
    critical as CRITICAL, \
    error as ERROR, \
    exception as EXCEPTION

import constants


####### LOGGING HELPERS #######
# We use root level logger (it is easy)
# You need only following import to use it
# from helpers import INFO
###############################

def setup_logging(log_level=logging.INFO, module_name=False):
    """Setup logging system
    """

    msg = (u'{}%(levelname)-8s [%(asctime)s]  %(message)s').format(
        u"%(filename)s:%(lineno)-5d # " if module_name else u"")

    logging.basicConfig(format=msg, level=log_level)


# Block end line
BLOCK_END = "+"*70


def print_block_end(func):
    """Prints 70 '+' chars after function call
    """
    def wrapper(*args, **kwargs):
        """Call function and print line
        """
        result = func(*args, **kwargs)
        INFO("")
        INFO(BLOCK_END)
        INFO("")

        return result

    return wrapper


# ####### SYSTEM HELPERS #######

def emergency_exit():
    """Immediately exit from script
    """
    ERROR("Script terminated")
    sys.exit(1)


def script_exit():
    """Exit from script
    """
    sys.exit(0)


def check_python_version():
    """Check Python version. If version < 2.7 then exit
    """
    if sys.version_info < (2, 7):
        print "You need use python 2.7 or greater"
        sys.exit(1)


def uuid():
    """Generate  UUID in lower case
    """
    return str(uuid4()).lower()


def json_load(data, default=None, critical=False):
    """Load JSON from string or file
    """
    try:
        return (json.loads if not hasattr(data, 'read') else json.load)(data)

    except ValueError:
        if critical:
            CRITICAL("Can't parse JSON data")
            EXCEPTION("")
            emergency_exit()

        else:
            ERROR("Can't parse JSON data")
            return default


def json_dump(data, fhandler=None, critical=False, default=None):
    """Dump data to JSON and write to string or file
    """
    try:
        if fhandler:
            json.dump(data, fhandler, indent=4)

        else:
            return json.dumps(data, indent=4)

    except ValueError:
        if critical:
            CRITICAL("Can't dump data to JSON")
            EXCEPTION("")
            emergency_exit()

        else:
            ERROR("Can't dump data to JSON")
            return default


####### FILE SYSTEM HELPERS #######

def build_path(*args):
    """Build path from list
    """
    return os.path.join(*args)


def erase_dir(path):
    """Remove all folders and files in dir @path
       except folder from @constants.DO_NOT_DELETE
    """
    DEBUG("Erasing '%s'", path)

    for node in os.listdir(path):
        if node in constants.DO_NOT_DELETE:
            continue

        node_path = os.path.join(path, node)
        (shutil.rmtree if os.path.isdir(node_path) else os.remove)(node_path)

    DEBUG("'%s' successfully erased", path)


def find_unic_path(path):
    """Find unic path
    """
    i = 1
    while os.path.exists("{0}{1}".format(path, i)):
        i += 1

    return "{0}{1}".format(path, i)


def create_folder(path, erase=False, quiet=False):
    """Create folder at @path.
    - @erase - erase existing folder
    - @quiet - don't ask user about particular actions
    - if @quiet is False, new folder with name @path[i]
      will be created
    - @erase has more priority than @quiet
    """
    # >:( a lot of returns - not good style

    DEBUG("Creating '%s' folder", path)

    try:
        os.makedirs(path)

    except OSError as ex:

        # we can't support other errors, except 'Folder already exists'
        if ex.errno != 17:
            CRITICAL("Can't create folder %s", path)
            EXCEPTION("")
            emergency_exit()

    else:
        DEBUG("Folder '%s' created", path)
        return path

    # Looks like folder already exists
    # lets try to erase it or create new
    # at different path

    ERROR("Can't create '%s' folder", path)
    if erase:
        try:
            erase_dir(path)

        except Exception:
            CRITICAL("Folder '%s' can't be erased")

        else:
            INFO("Folder erased: '{}'".format(path))
            return path

    # Well, erase == False or folder can't be erased
    if not quiet:
        answ = ''

        while not answ:
            answ = raw_input(("Type (E) to erase existing folder, "
                              "type (Q) to exit the script "
                              "or enter new folder name: ")).lower()

            if answ == "e":
                return create_folder(path, erase=True, quiet=quiet)

            elif answ == "q":
                script_exit()

            elif answ:
                return create_folder(answ, erase=False, quiet=quiet)

    else:
        return create_folder(find_unic_path(path), erase=erase, quiet=quiet)


def read_file(path):
    """Read file
    """
    try:
        with open_file(path) as handler:
            return handler.read()

    except Exception:
        CRITICAL("Can't read file '%s'", path)
        EXCEPTION("")
        emergency_exit()


def open_file(path, mode="rb"):
    """Open file
    """
    try:
        return open(path, mode)

    except Exception:
        CRITICAL("Can't open file '%s'", path)
        EXCEPTION("")
        emergency_exit()


####### DATA HELPERS #######

def clean_data(data, strip=True):
    if len(set(data) - set(["\n", "\t"])) > 0:
        return data.strip("\n\t\r") if strip else data

    else:
        return ""


def encode(data, encoding="utf-8"):
    return data.encode(encoding)


def decode(data, encoding="utf-8"):
    return data.decode(encoding)


def convert_to_regexp(patterns):
    """Return list of regexp objects
    """
    regexp_list = []
    for pattern in patterns:
        try:
            regexp_list.append(re.compile(pattern, re.I))
        except Exception:
            ERROR("Invalid pattern: %s", pattern)
            emergency_exit()

    return regexp_list


def check_by_regexps(data, regexp_list):
    """Check data using regexp
    """
    for regexp in regexp_list:
        if regexp.search(data):
            return True

    else:
        return False
