#!/usr/bin/env python
# encoding: utf-8


import argparse
import base64
import logging
import os

from uuid import UUID

import constants
from helpers import setup_logging, DEBUG, INFO, ERROR, CRITICAL, \
    check_python_version, script_exit, uuid as gen_guid, \
    json_load, open_file, clean_data, encode, emergency_exit, \
    BLOCK_END, print_block_end


# Global variable for output
OUTPUT_IO = None


def check_data(data):
    return '"' in data or \
           "'" in data or \
           "<" in data or \
           ">" in data or \
           "\n" in data or \
           "&" in data


def cdata(data, force=False):
    if not data.strip() and not force:
        return data

    if force or check_data(data):
        return "<![CDATA[{}]]>".format(data.replace("]]>", "]]]]><![CDATA[>"))

    return data


def write_xml(tagname, attrs=None, data=None, close=False, indent=0, force_cdata=False, closing=False):
    OUTPUT_IO.write("{indent}<{closing}{tagname}{attrs}{close}>{data}{closetag}{newline}".format(
        indent=" "*indent,
        tagname=tagname,
        attrs="" if not attrs else (" "+" ".join(['{}="{}"'.format(k, v) for k, v in attrs.items()])),
        close="/" if close and data is None else "",
        closetag="</{}>".format(tagname) if close and data is not None else "",
        data=cdata(data, force_cdata) if data is not None else "",
        newline="\n" if close or data is None else "",
        closing="/" if closing else ""
    ))


@print_block_end
def write_app_info(config):

    INFO("Application Information Data: Processing...")

    info_path = os.path.join(config["source"], constants.INFO_FILE)

    with open_file(info_path) as info_file:
        info_json = json_load(info_file, critical=True)

    write_xml("Information", indent=2)

    for tagname, value in info_json.items():
        write_xml(tagname, data=value, close=True, indent=4)

    write_xml("Information", indent=2, closing=True)

    INFO("Application Information Data: Done!")


@print_block_end
def write_e2vdom(config):

    INFO("E2VDOM Data: Processing...")

    write_xml("E2vdom", indent=2)

    pages_path = os.path.join(config["source"], constants.PAGES_FOLDER)

    all_events = []
    all_actions = []

    for name in os.listdir(pages_path):
        e2vdom_path = os.path.join(pages_path, name, constants.E2VDOM_FILE)

        DEBUG("Open file: %s", e2vdom_path)

        with open_file(e2vdom_path) as e2vdom_file:
            e2vdom = json_load(e2vdom_file, critical=True)
            all_events.extend(e2vdom["events"])
            all_actions.extend(e2vdom["actions"])

    INFO("E2VDOM Data: Writing events")

    write_xml("Events", indent=4)

    for event in all_events:
        actions = event.pop("actions", [])
        write_xml("Event", attrs=event, indent=6)

        for action in actions:
            write_xml(
                "Action",
                attrs={"ID": action},
                indent=8,
                data="",
                close=True
            )

        write_xml("Event", indent=6, closing=True)

    write_xml("Events", indent=4, closing=True)

    INFO("E2VDOM Data: Events done!")
    INFO("E2VDOM Data: Writing actions")

    write_xml("Actions", indent=4)

    for action in all_actions:

        params = action.pop("Params", [])
        write_xml("Action", attrs=action, indent=6)

        for key, value in params:
            write_xml(
                "Parameter",
                attrs={"ScriptName": key},
                indent=8,
                data=value,
                close=True
            )

        write_xml("Action", indent=6, closing=True)

    write_xml("Actions", indent=4, closing=True)
    write_xml("E2vdom", indent=2, closing=True)

    INFO("E2VDOM Data: Actions done!")
    INFO("E2VDOM Data: Done!")


@print_block_end
def write_libraries(config):

    INFO("Libraries Data: Processing...")

    libs_path = os.path.join(config["source"], constants.LIBRARIES_FOLDER)
    if not os.path.exists(libs_path):
        CRITICAL("Can't find: {}".format(libs_path))
        emergency_exit()

    write_xml("Libraries", indent=2)

    files = list(set(os.listdir(libs_path)) - set(constants.RESERVED_NAMES))
    for lib_name in sorted(files):
        lib_path = os.path.join(libs_path, lib_name)

        if not os.path.isfile(lib_path):
            continue

        DEBUG("Open file: %s", lib_path)
        with open_file(lib_path) as lib_f:
            write_xml(
                tagname="Library",
                attrs={"Name": lib_name.split(".", 1)[0]},
                indent=4,
                data=lib_f.read(),
                close=True
            )

    write_xml("Libraries", indent=2, closing=True)
    INFO("Libraries Data: Done!")


@print_block_end
def write_resources(config):

    INFO("Resources Data: Processing...")

    resources_path = os.path.join(config["source"], constants.RESOURCES_FOLDER)
    if not os.path.exists(resources_path):
        CRITICAL("Can't find: {}".format(resources_path))
        emergency_exit()

    write_xml("Resources", indent=2)

    files = list(set(os.listdir(resources_path)) - set(constants.RESERVED_NAMES))
    for res_name in sorted(files):
        res_path = os.path.join(resources_path, res_name)

        if not os.path.isfile(res_path):
            continue

        raw_name = res_name.split("_", 2)

        try:
            res_guid = UUID(raw_name[0])

        except ValueError:
            res_guid = gen_guid()
            res_type = res_name.rsplit(".", 1)
            res_type = res_type[1] if len(res_type) == 2 else "res"

        else:
            res_type = raw_name[1]
            res_name = raw_name[2]

        attrs = {
            "ID": res_guid,
            "Name": res_name,
            "Type": res_type
        }

        DEBUG("Open file: %s", res_path)
        with open_file(res_path) as res_f:
            write_xml(
                tagname="Resource",
                attrs=attrs,
                indent=4,
                data=base64.b64encode(res_f.read()),
                close=True
            )

    write_xml("Resources", indent=2, closing=True)
    INFO("Resources Data: Done!")


@print_block_end
def write_databases(config):
    INFO("Databases Data: Processing...")

    dbs_path = os.path.join(config["source"], constants.DATABASES_FOLDER)
    if not os.path.exists(dbs_path):
        CRITICAL("Can't find: {}".format(dbs_path))
        emergency_exit()

    write_xml("Databases", indent=2)

    files = list(set(os.listdir(dbs_path)) - set(constants.RESERVED_NAMES))
    for db_name in sorted(files):
        db_path = os.path.join(dbs_path, db_name)

        if not os.path.isfile(db_path):
            continue

        raw_name = db_name.split("_", 1)

        try:
            db_guid = UUID(raw_name[0])

        except ValueError:
            db_guid = gen_guid()

        raw_name = raw_name[-1].split(".", 1)
        db_name = raw_name[0]
        db_type = raw_name[1] if len(raw_name) == 2 else "sqlite"

        attrs = {
            "ID": db_guid,
            "Name": db_name,
            "Type": db_type
        }

        DEBUG("Open file: %s", db_path)
        with open_file(db_path) as db_f:
            write_xml(
                tagname="Database",
                attrs=attrs,
                indent=4,
                data=base64.b64encode(db_f.read()),
                close=True
            )

    write_xml("Databases", indent=2, closing=True)
    INFO("Databases Data: Done!")


@print_block_end
def write_structure(config):

    INFO("Structure Data: Processing...")

    structure_path = os.path.join(config["source"], constants.STRUCT_FILE)

    if not os.path.exists(structure_path):
        ERROR("Can't find: {}".format(structure_path))
        write_xml("Structure", indent=2, close=True)
        return

    write_xml("Structure", indent=2)

    with open_file(structure_path) as struct_file:
        struct_json = json_load(struct_file, critical=True)

    for obj in struct_json:
        write_xml("Object", attrs=obj, data="", close=True, indent=4)

    write_xml("Structure", indent=2, closing=True)

    INFO("Structure Data: Done!")


@print_block_end
def write_security(config):

    INFO("Security Data: Processing...")

    security_path = os.path.join(config["source"], constants.SECURITY_FOLDER)

    if not os.path.exists(security_path):
        CRITICAL("Can't find: {}".format(security_path))
        emergency_exit()

    groups_and_users_path = \
        os.path.join(security_path, constants.USERS_GROUPS_FILE)

    with open_file(groups_and_users_path) as ug_file:
        ug_json = json_load(ug_file, critical=True)

    write_xml("Security", indent=2)
    write_xml("Groups", indent=4, close=True)
    write_xml("Users", indent=4)

    INFO("Security Data: Writing users")

    for user in ug_json.get("users", []):

        write_xml("User", indent=6)

        for key, value in user.items():
            if key == "Rights":
                write_xml("Rights", indent=8)
                for right in value:
                    write_xml(
                        "Right",
                        attrs=right,
                        indent=10,
                        close=True
                    )
                write_xml("Rights", indent=8, closing=True)

            else:
                write_xml(
                    key,
                    data=value,
                    indent=8,
                    close=True,
                    force_cdata=True
                )

        write_xml("User", indent=6, closing=True)

    write_xml("Users", indent=4, closing=True)

    INFO("Security Data: Users done!")
    INFO("Security Data: Writing LDAP")

    ldap_path = os.path.join(security_path, constants.LDAP_LDIF)
    if os.path.exists(ldap_path):
        with open_file(ldap_path) as ldap_file:
            write_xml(
                "LDAP",
                indent=4,
                data=base64.b64encode(ldap_file.read()),
                close=True
            )

    else:
        write_xml("LDAP", indent=4, data="", close=True)

    write_xml("Security", indent=2, closing=True)

    INFO("Security Data: Done!")


@print_block_end
def write_pages(config):

    INFO("Pages Data: Processing...")

    pages_path = os.path.join(config["source"], constants.PAGES_FOLDER)

    if not os.path.exists(pages_path):
        CRITICAL("Can't find: {}".format(pages_path))
        emergency_exit()

    write_xml("Objects", indent=2)
    for page in sorted(os.listdir(pages_path)):
        walk(pages_path, page, indent=4)

    write_xml("Objects", indent=2, closing=True)


    actions_path = os.path.join(config["source"], constants.APP_ACTIONS_FOLDER)
    if os.path.exists(actions_path):
        write_actions(actions_path, 2)
    else:
        write_xml("Actions", indent=2)
        write_xml("Actions", indent=2, closing=True)

    INFO("Pages Data: Done!")


def walk(path, name, indent):
    new_path = os.path.join(path, name)
    actions_folder = "Actions-{}".format(name)

    info_path = os.path.join(new_path, constants.INFO_FILE)
    if not os.path.exists(info_path):
        CRITICAL("Can't find: {}".format(info_path))
        emergency_exit()

    with open_file(info_path) as info_file:
        info_json = json_load(info_file, critical=True)

    write_xml("Object", attrs=info_json["attrs"], indent=indent)
    write_actions(os.path.join(new_path, actions_folder), indent+2)
    write_xml("Objects", indent=indent+2)

    nodes = list(set(os.listdir(new_path)) - set(constants.RESERVED_NAMES) - {actions_folder})
    for name in sorted(nodes):
        if os.path.isdir(os.path.join(new_path, name)):
            walk(new_path, name, indent+4)

        else:
            write_object(new_path, name, indent+4)

    write_xml("Objects", indent=indent+2, closing=True)
    write_attributes(info_json["attributes"], indent+2)
    write_xml("Object", indent=indent, closing=True)


def write_actions(path, indent):
    actions_map_path = os.path.join(path, constants.MAP_FILE)

    if not os.path.exists(actions_map_path):
        CRITICAL("Can't find: %s", actions_map_path)
        emergency_exit()

    with open_file(actions_map_path) as actions_map_file:
        actions_map = json_load(actions_map_file, critical=True)

    write_xml("Actions", indent=indent)

    for action_name in sorted(os.listdir(path)):
        action_path = os.path.join(path, action_name)
        if not os.path.isfile(action_path) or \
                action_name in constants.RESERVED_NAMES:

            continue

        attrs = actions_map.get(action_name, None)
        if not attrs:
            attrs = {
                "Top": "",
                "State": "",
                "Left": "",
                "ID": str(gen_guid()),
                "Name": action_name.split(".", 1)[0],
            }

        with open_file(action_path) as action_f:
            write_xml(
                tagname="Action",
                attrs=attrs,
                indent=indent+2,
                data=action_f.read(),
                close=True,
                force_cdata=True
            )

    write_xml("Actions", indent=indent, closing=True)


def write_object(path, name, indent):
    with open_file(os.path.join(path, name)) as obj_file:
        obj_json = json_load(obj_file, critical=True)

    write_xml("Object", attrs=obj_json["attrs"], indent=indent)
    write_xml("Actions", indent=indent+2, data="", close=True)
    write_xml("Objects", indent=indent+2, data="", close=True)
    write_attributes(obj_json["attributes"], indent+2)
    write_xml("Object", indent=indent, closing=True)


def write_attributes(attributes, indent):
    write_xml("Attributes", indent=indent)
    for key, value in attributes.items():
        write_xml(
            "Attribute",
            attrs={"Name": key},
            data=clean_data(encode(value)),
            indent=indent+2,
            close=True
        )
    write_xml("Attributes", indent=indent, closing=True)


def build(config):
    """Build function
    """
    global OUTPUT_IO

    if not os.path.isdir(config["source"]):
        ERROR("Can't find %s", config["source"])
        return

    OUTPUT_IO = open_file(config["target"]["path"], "wb")
    OUTPUT_IO.write(
        """<?xml version="1.0" encoding="utf-8"?>\n"""
        """<Application>\n"""
    )

    write_app_info(config)
    write_pages(config)
    write_e2vdom(config)
    write_libraries(config)
    # write_structure(config)

    OUTPUT_IO.write("""  <Structure/>\n""")
    OUTPUT_IO.write("""  <Backupfiles/>\n""")

    write_resources(config)
    write_databases(config)
    write_security(config)

    OUTPUT_IO.write("</Application>")
    OUTPUT_IO.close()


def main():
    """Main function
    """
    args_parser = argparse.ArgumentParser()

    args_parser.add_argument("source", type=str,
                             help="aplication source folder")

    args_parser.add_argument("target", type=str,
                             help="target XML file")

    args_parser.add_argument("-v", "--verbosity", action="count",
                             help="be more verbose",
                             default=0)

    args = args_parser.parse_args()

    # Setup logging system and show necessary messages
    setup_logging(logging.INFO if args.verbosity == 0 else logging.DEBUG,
                  module_name=True if args.verbosity > 1 else False)

    INFO("")
    INFO("Information logging turned on")
    DEBUG("Debug logging turned on")
    INFO("")
    INFO(BLOCK_END)
    INFO("")

    config = {
        "target": {
            "path": args.target,
        },
        "source": args.source
    }

    # Main process starting
    build(config)

    INFO("\nPath to application XML:\n{}".format(config["target"]["path"]))


if __name__ == "__main__":
    check_python_version()
    main()
    script_exit()
