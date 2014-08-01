#!/usr/bin/env python
# encoding: utf-8


import argparse
import logging
import os
import re
import shutil

# from functools import partial
from uuid import UUID

import constants
from helpers import setup_logging, DEBUG, INFO, ERROR, \
    check_python_version, script_exit, \
    create_folder, uuid as gen_guid, json_load, \
    open_file as fopen, json_dump, \
    convert_to_regexp, check_by_regexps


RE_RES_UUID = re.compile("[0-F]{8}-[0-F]{4}-[0-F]{4}-[0-F]{4}-[0-F]{12}", re.I)
RE_OBJ_UUID = re.compile("[0-F]{8}[-_][0-F]{4}[-_][0-F]{4}[-_][0-F]{4}[-_][0-F]{12}", re.I)


GUIDS_TO_REPLACE = {}


def re_res_sub(resources):
    """Regexp sub pattern function
    """

    def func(match, *args, **kwargs):
        """Processing match objects. Replacing resources GUIDs.
        """

        data = match.group(0)
        return (resources[data], True) if data in resources else (data, False)

    return func


def re_obj_sub(objects):
    """Regexp sub pattern function
    """

    def func(match, create_new=False, *args, **kwargs):
        """Processing match objects. Replacing objects GUIDs.
        """

        data = match.group(0)

        if create_new:
            dash = data.replace("_", "-") if "_" in data else data

            if dash not in objects:
                new = gen_guid()
                objects[dash] = new
                objects[dash.replace("-", "_")] = new.replace("-", "_")

        if data in objects:
            return (objects[data], True)

        return (data, False)

    return func


def sub_chain_func(chain):
    """Regexp sub pattern function
    """

    def func(match, *args, **kwargs):
        """Processing match objects
        """

        for sub_func in chain:
            result = sub_func(match, *args, **kwargs)
            if result[1]:
                return result[0]

        return match.group(0)

    return func


def normalize_path(path, config):
    """Replace alias with real path
    """

    for alias, link in config["Aliases"].items():
        if path.startswith(alias):
            return path.replace(alias, link, 1)

    return path


def open_file(path, config):
    """Normalize path and open file
    """

    return fopen(normalize_path(path, config))


def create_basic_structure(config):
    """Create basic folders
    """

    DEBUG("Creating basic structure")

    root = config["target"]["path"] = create_folder(**config["target"])

    for folder in constants.BASE_FOLDERS:
        create_folder(os.path.join(root, folder))

    INFO("Basic structure successfully created")


def copy_files(target, sources, config):
    """Copy files
    """

    if not isinstance(sources, (list, tuple)):
        sources = (sources,)

    copied_files = []

    for source in sources:

        path = ""
        params = {
            "rename": None,
            "exclude": None,
            "include": None
        }

        # it can be single file or folder
        # with additional params like rename,
        # exclude, include
        if isinstance(source, dict):
            path = normalize_path(source["path"], config)

            for param in params:
                params[param] = val = source.get(param, None)
                if val and not isinstance(val, (list, tuple, dict)):
                    params[param] = (val,)

            if params["exclude"]:
                params["exclude"] = convert_to_regexp(params["exclude"])

            if params["include"]:
                params["include"] = convert_to_regexp(params["include"])

        # it can be single file or folder
        # without additional params
        else:
            path = normalize_path(source, config)

        # fetch all files if @path is directory
        if os.path.isdir(path):
            files = os.listdir(path)

        # else split @path to parent path and file name
        else:
            path, name = os.path.split(path.rstrip("\/"))
            files = (name,)

        for name in files:

            source_path = os.path.join(path, name)
            if os.path.isdir(source_path):
                DEBUG("Directories are not supported: {}".format(source_path))
                continue

            # if file in exclude list - continue
            if params["exclude"] and check_by_regexps(name, params["exclude"]):
                continue

            # if file not in include list - continue
            if params["include"] and not check_by_regexps(name, params["include"]):
                continue

            # if file in rename list - rename it, else use source name
            if params["rename"] and \
               (name in params["rename"] or len(files) == 1):

                if isinstance(params["rename"], (tuple, list)):
                    new_name = params["rename"][0]

                else:
                    new_name = params["rename"].get(name, name)

            else:
                new_name = name

            target_path = os.path.join(target, new_name)

            if os.path.exists(source_path):
                DEBUG("Copy '%s' to '%s'", source_path, target_path)
                shutil.copy2(source_path, target_path)
                copied_files.append(new_name)

            else:
                ERROR("No such file or directory: '{}'".format(source_path))

    return copied_files


def copy_resources(config):
    """Copy resources
    """

    if "Resources" not in config:
        INFO("No information about resources")
        return

    DEBUG("Collect resources info")

    target_path = os.path.join(config["target"]["path"],
                               constants.RESOURCES_FOLDER)

    DEBUG("Copy resources")

    sources = config["Resources"]
    if not isinstance(sources, (list, tuple)):
        sources = (sources,)

    for source in sources:

        files = copy_files(target_path, source, config)

        change_guids = False
        if isinstance(source, dict):
            change_guids = bool(source.get("generateGUIDs", False))

        if not change_guids:
            continue

        for old_name in files:

            raw_name = old_name.split("_", 2)

            try:
                res_guid = UUID(raw_name[0])

            except ValueError:
                res_guid = gen_guid()
                res_type = res_name.rsplit(".", 1)
                res_type = res_type[1] if len(res_type) == 2 else "res"

            else:
                res_type = raw_name[1]
                res_name = raw_name[2]

            new_guid = GUIDS_TO_REPLACE[res_guid] = gen_guid()
            new_name = "{}_{}_{}".format(new_guid, res_type, res_name)

            old_path = os.path.join(target_path, old_name)
            new_path = os.path.join(target_path, new_name)

            DEBUG("Move '%s' to '%s'", old_path, new_path)
            shutil.move(old_path, new_path)

    INFO("Resources were copied successfully")


def copy_libraries(config):
    """Copy libraries
    """

    if "Libraries" not in config:
        INFO("No information about libraries")
        return

    DEBUG("Collect libraries info")

    target_path = os.path.join(config["target"]["path"],
                               constants.LIBRARIES_FOLDER)

    DEBUG("Copy libraries")

    copy_files(target_path, config["Libraries"], config)

    INFO("Libraries were copied successfully")


def copy_security(config):
    """Copy security section
    """

    if "Security" not in config:
        INFO("No information about security settings")
        return

    DEBUG("Collect security info")

    target_path = os.path.join(config["target"]["path"],
                               constants.SECURITY_FOLDER)

    DEBUG("Copy security settings")

    copy_files(target_path, config["Security"], config)

    INFO("Security settings were copied successfully")


def copy_app_actions(config):
    """Copy application actions
    """

    if "Actions" not in config:
        INFO("No information about application actions")
        return

    DEBUG("Collect application actions info")

    target_path = os.path.join(config["target"]["path"],
                               constants.APP_ACTIONS_FOLDER)

    DEBUG("Copy application actions")

    copy_files(target_path, config["Actions"], config)

    INFO("Application actions were copied successfully")


def copy_databases(config):
    """Copy databases
    """

    if "Databases" not in config:
        INFO("No information about databases")
        return

    DEBUG("Collect databases info")

    target_path = os.path.join(config["target"]["path"],
                               constants.DATABASES_FOLDER)

    DEBUG("Copy databases")

    copy_files(target_path, config["Databases"], config)

    INFO("Databases were copied successfully")


def copy_pages(config):
    """Copy pages and change resources and objects GUIDs
    """

    if "Pages" not in config:
        INFO("No information about pages")
        return

    target_path = os.path.join(config["target"]["path"],
                               constants.PAGES_FOLDER)

    pages = config["Pages"]
    resources = config["Resources"]

    if not isinstance(pages, (list, tuple)):
        pages = (pages,)

    new_pages = []
    for page in pages:
        if isinstance(page, (str, unicode)):
            page = {
                "path": page
            }

        if not page["path"].rstrip("\/").lower().endswith("pages"):
            new_pages.append(page)

        else:
            page["path"] = normalize_path(page["path"], config)
            if not os.path.exists(page["path"]):
                ERROR("No such directory: '%s'", page["path"])
                continue

            for folder in os.listdir(page["path"]):
                folder_path = os.path.join(page["path"], folder)

                if not os.path.isdir(folder_path):
                    ERROR("Page can't be file: %s", folder_path)
                    continue

                new_page = page.copy()
                new_page["path"] = folder_path
                new_pages.append(new_page)

    for page in new_pages:

        if isinstance(page, (str, unicode)):
            page = {
                "path": page
            }

        # normalize path - replace alias with real path
        page["path"] = normalize_path(page["path"], config)
        if not os.path.exists(page["path"]):
            ERROR("No such directory: '{}'".format(page["path"]))
            continue

        # if name not defined - got it from folder name
        if not page.get("name", ""):
            page["name"] = os.path.split(page["path"].rstrip("\/"))[1]
            page["rename"] = False

        copy_path = os.path.join(target_path, page["name"])
        if os.path.exists(copy_path):
            ERROR("Directory already exists: '{}'".format(copy_path))
            continue

        if page.get("mode", "") not in ("move", "copy"):
            page["mode"] = "move"

        # copy page to new folder
        DEBUG("Copy '{}' to '{}'".format(page["path"], copy_path))
        shutil.copytree(page["path"], copy_path)

        info_path = os.path.join(copy_path, constants.INFO_FILE)
        with fopen(info_path, "rb") as hdlr:
            info = json_load(hdlr, critical=True)

        if page.get("rename", True):
            info["attrs"]["Name"] = page["name"]

        with fopen(info_path, "wb") as hdlr:
            json_dump(info, hdlr, critical=True)

        # if page not copied continue, else need to change all guids to new
        if page["mode"] == "move" and not resources:
            continue

        chain, regexp = [], None

        if resources:
            chain.append(re_res_sub(resources))
            regexp = RE_RES_UUID

        if page["mode"] == "copy":
            new_id = gen_guid()
            objects = {
                info["attrs"]["ID"]: new_id,
                info["attrs"]["ID"].replace("-", "_"): new_id.replace("-", "_")
            }
            chain.append(re_obj_sub(objects))
            regexp = RE_OBJ_UUID

        # function for guids replacement
        sub_func = sub_chain_func(chain)

        for current, subfolder, files in os.walk(copy_path):

            # objects files at first, then python files
            for node in sorted(files, key=lambda f: os.path.splitext(f.rstrip("\/"))[1]):

                node_path = os.path.join(current, node)
                with open(node_path, "rb") as src:
                    data = src.read()

                with open(node_path, "wb") as dst:
                    dst.write(regexp.sub(sub_func, data))

        # if page.get("rename", True):
        #     info_path = os.path.join(copy_path, constants.INFO_FILE)
        #     with fopen(info_path, "rb") as f:
        #         info = json_load(f)

        #     info["attrs"]["Name"] = page["name"]

        #     with fopen(info_path, "wb") as f:
        #         json_dump(info, f)

        # # if page not copied continue, else need to change all guids to new
        # if page["mode"] == "move" and not resources:
        #     continue

        # chain, regexp = [], None

        # if resources:
        #     chain.append(re_res_sub(resources))
        #     regexp = RE_RES_UUID

        # if page["mode"] == "copy":
        #     chain.append(re_obj_sub({}))
        #     regexp = RE_OBJ_UUID

        # sub_func = sub_chain_func(chain)

        # for current, subfolder, files in os.walk(copy_path):

        #     # objects files at first, then python files
        #     for node in sorted(files, key=lambda f: os.path.splitext(f)[1]):

        #         node_path = os.path.join(current, node)
        #         create_new_guid = os.path.splitext(node)[1] != ".py"

        #         with open(node_path, "rb") as src:
        #             data = src.read()

        #         with open(node_path, "wb") as dst:
        #             dst.write(regexp.sub(partial(sub_func,
        #     create_new=create_new_guid), data))

    INFO("Pages were copied successfully")


def create_application_info_file(config):
    """Create __info__.json in root directory
    """
    DEBUG("Collect application info")

    app_info = config.get("ApplicationInfo", {})

    # Load existing config file or create empty
    if "BaseConfigFile" in app_info:
        with open_file(app_info.pop("BaseConfigFile"), config) as hdlr:
            info = json_load(hdlr)

    else:
        info = dict(ID=gen_guid(), Name="Application", Description="",
                    Owner="-", Active="1", Serverversion="",
                    ScriptingLanguage="python", Icon="")

    # Update values from config
    for key, value in app_info.items():
        info[key] = value

    # Generate new GUID if it isn't exiisting
    if not info.get("ID", ""):
        info["ID"] = gen_guid()

    # Write data to file
    path = os.path.join(config["target"]["path"], constants.INFO_FILE)

    DEBUG("Writing application info to '%s'", path)

    with fopen(path, "wb") as hdlr:
        json_dump(info, hdlr)

    INFO("Application info successfully written to '%s'", path)


def make(config):
    """Call copy functions in cycle
    """
    # Create child folders
    for func in (create_basic_structure,
                 copy_resources,
                 copy_libraries,
                 copy_databases,
                 copy_security,
                 copy_app_actions,
                 copy_pages,
                 create_application_info_file):

        INFO("")
        INFO("+"*70)
        INFO("")
        func(config)


def main():
    """Main function
    """
    args_parser = argparse.ArgumentParser()

    args_parser.add_argument("cfg", type=argparse.FileType("rb"),
                             help="configuration file")

    args_parser.add_argument("target", type=str,
                             help="target folder")

    args_parser.add_argument("-v", "--verbosity", action="count",
                             help="be more verbose",
                             default=0)

    args_parser.add_argument("-e", "--erase", action="store_true",
                             help="erase target folder")

    args_parser.add_argument("-q", "--quiet", action="store_true",
                             help="no user interaction")

    args = args_parser.parse_args()

    # Setup logging system and show necessary messages
    setup_logging(logging.INFO if args.verbosity == 0 else logging.DEBUG,
                  module_name=True if args.verbosity > 1 else False)

    INFO("Information logging turned on")
    DEBUG("Debug logging turned on")

    # Parsing config file
    DEBUG("Parsing config file")

    config = json_load(args.cfg, critical=True)

    INFO("Config file parsed successfully")

    config["target"] = {
        "path": args.target,
        "erase": args.erase,
        "quiet": args.quiet,
    }

    # Main process starting
    make(config)

    INFO("")
    INFO("+"*70)
    INFO("\nPath to application:\n{}".format(config["target"]["path"]))


if __name__ == "__main__":
    check_python_version()
    main()
    script_exit()
