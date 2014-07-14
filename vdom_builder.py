#!/usr/bin/python
# encoding: utf-8

import base64
import collections
import cStringIO
import json
import os
import sys
import xml

from uuid import uuid4 as uuid

__version__ = "0.0.1"


INFO_JSON = "__info__.json"
E2VDOM_JSON = "__e2vdom__.json"
MAP_JSON = "__map__.json"
USERS_JSON = "__users__.json"
GROUPS_JSON = "__groups__.json"
STRUCT_JSON = "__struct__.json"
LDAP_LDIF = "__ldap__.ldif"
INIT_PY = "__init__.py"

RESERVED_NAMES = (
    INFO_JSON,
    E2VDOM_JSON,
    MAP_JSON,
    USERS_JSON,
    GROUPS_JSON,
    LDAP_LDIF,
    INIT_PY
)


def encode(data):
    return data.encode("utf-8")


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
        return "<![CDATA[{}]]>".format(data.replace("]]>", "]]]]><![CDATA["))

    return data


def clear_data(data):
    if len(set(data) - set(["\n", "\t"])) > 0:
        return data
    else:
        return ""


class Builder(object):

    __instance = None

    def __new__(cls, *a, **kwa):
        if cls.__instance is None:
            cls.__instance = object.__new__(cls)
        return cls.__instance

    def initialize(
        self,
        src="",
        dst="",
        debug=False,
        library="",
        library_copy_mode=""
    ):

        self.debug = debug
        self.src = src
        self.dst = dst
        self.library = library
        self.library_copy_mode = library_copy_mode
        self.output = None
        return self

    def start(self):
        """Setup logging and start main process
        """
        self.dst = self.dst or os.path.basename(os.path.normpath(self.src))

        if not os.path.isdir(self.src):
            raise Exception("{} is not a folder".format(self.src))

        # if os.path.exists(self.dst):
        #     raise Exception("{} already exists".format(self.dst))

        self.output = open(self.dst, "w")
        self.build()

        print "Save application to {}".format(self.dst)

    def build(self):
        """Finish parsing process and print statistics
        """
        self.output.write("""<?xml version="1.0" encoding="utf-8"?>\n<Application>\n""")

        self.write_app_info()
        self.write_pages()
        self.write_e2vdom()
        self.write_libraries()
        self.write_structure()

        self.output.write("""  <Backupfiles/>\n""")

        self.write_resources()
        self.write_databases()
        self.write_security()

        self.output.write("</Application>")

    def open_file(self, path, mode="r"):
        print "Open {}".format(path)
        return open(path, mode)

    def write_xml(
        self,
        tagname,
        attrs=None,
        data=None,
        close=False,
        indent=0,
        force_cdata=False,
        closing=False
    ):
        self.output.write("{indent}<{closing}{tagname}{attrs}{close}>{data}{closetag}{newline}".format(
            indent=" "*indent,
            tagname=tagname,
            attrs="" if not attrs else (" "+" ".join(['{}="{}"'.format(k, v) for k, v in attrs.items()])),
            close="/" if close and data is None else "",
            closetag="</{}>".format(tagname) if close and data is not None else "",
            data=cdata(data, force_cdata) if data is not None else "",
            newline="\n" if close or data is None else "",
            closing="/" if closing else ""
        ))

    def write_app_info(self):
        info_path = os.path.join(self.src, INFO_JSON)

        if not os.path.exists(info_path):
            raise Exception("Can't find {}".format(info_path))

        self.write_xml("Information", indent=2)

        with self.open_file(info_path) as info_file:
            info_json = json.load(info_file)

        for tagname, value in info_json.items():
            self.write_xml(tagname, data=value, close=True, indent=4)

        self.write_xml("Information", indent=2, closing=True)

    def write_e2vdom(self):
        self.write_xml("E2vdom", indent=2)

        pages_path = os.path.join(self.src, "Pages")

        all_events = []
        all_actions = []

        for name in os.listdir(pages_path):
            e2vdom_path = os.path.join(pages_path, name, E2VDOM_JSON)
            if os.path.exists(e2vdom_path):

                with self.open_file(e2vdom_path) as e2vdom_file:
                    e2vdom = json.load(e2vdom_file)
                    all_events.extend(e2vdom["events"])
                    all_actions.extend(e2vdom["actions"])

        self.write_xml("Events", indent=4)

        for event in all_events:
            actions = event.pop("actions")
            self.write_xml("Event", attrs=event, indent=6)

            for action in actions:
                self.write_xml(
                    "Action",
                    attrs={"ID": action},
                    indent=8,
                    data="",
                    close=True
                )

            self.write_xml("Event", indent=6, closing=True)

        self.write_xml("Events", indent=4, closing=True)
        self.write_xml("Actions", indent=4)

        for action in all_actions:
            params = action.pop("params")
            self.write_xml("Action", attrs=action, indent=6)

            for param in params:
                self.write_xml(
                    "Parameter",
                    attrs={"ScriptName": param[0]},
                    indent=8,
                    data=param[1],
                    close=True
                )

            self.write_xml("Action", indent=6, closing=True)

        self.write_xml("Actions", indent=4, closing=True)
        self.write_xml("E2vdom", indent=2, closing=True)

    def write_libraries(self):
        self.write_xml("Libraries", indent=2)

        files_to_copy = []
        libs_path = os.path.join(self.src, "Libraries")

        if self.library and self.library_copy_mode == "instead":
            libs_path = self.library

        elif self.library and self.library_copy_mode == "replace":
            if not os.path.exists(self.library):
                raise Exception("Can't find {}".format(self.library))

            files_to_copy = os.listdir(self.library)

        if not os.path.exists(libs_path):
            raise Exception("Can't find {}".format(libs_path))

        libs_from_origin = \
            list(set(os.listdir(libs_path)) - set(files_to_copy))

        self._write_libs(libs_path, libs_from_origin)
        if files_to_copy:
            self._write_libs(self.library, files_to_copy)

        self.write_xml("Libraries", indent=2, closing=True)

    def _write_libs(self, path, libs_list):
        for lib_name in libs_list:
            p = os.path.join(path, lib_name)

            if not os.path.isfile(p) or \
               lib_name in RESERVED_NAMES:

                continue

            with self.open_file(p) as lib_f:
                self.write_xml(
                    tagname="Library",
                    attrs={"Name": lib_name.split(".")[0]},
                    indent=4,
                    data=lib_f.read(),
                    close=True
                )

    def write_resources(self):
        self.write_xml("Resources", indent=2)

        resources_path = os.path.join(self.src, "Resources")
        if not os.path.exists(resources_path):
            raise Exception("Can't find {}".format(resources_path))

        with self.open_file(os.path.join(resources_path, MAP_JSON)) as map_f:
            res_map = json.load(map_f)

        for res_name in os.listdir(resources_path):
            p = os.path.join(resources_path, res_name)

            if not os.path.isfile(p) or res_name in RESERVED_NAMES:
                continue

            attrs = res_map.get(res_name, None)
            if not attrs:
                attrs = {
                    "ID": str(uuid()),
                    "Name": res_name,
                    "Type": ""
                }

            with self.open_file(p) as res_f:
                self.write_xml(
                    tagname="Resource",
                    attrs=attrs,
                    indent=4,
                    data=base64.b64encode(res_f.read()),
                    close=True
                )

        self.write_xml("Resources", indent=2, closing=True)

    def write_databases(self):
        self.write_xml("Databases", indent=2)

        dbs_path = os.path.join(self.src, "Databases")
        if not os.path.exists(dbs_path):
            raise Exception("Can't find {}".format(dbs_path))

        with self.open_file(os.path.join(dbs_path, MAP_JSON)) as db_map_file:
            db_map = json.load(db_map_file)

        for db_name in os.listdir(dbs_path):
            p = os.path.join(dbs_path, db_name)

            if not os.path.isfile(p) or db_name in RESERVED_NAMES:
                continue

            attrs = db_map.get(db_name, None)
            if not attrs:
                attrs = {
                    "ID": str(uuid()),
                    "Name": db_name.split(".")[0],
                    "Type": "sqlite"
                }

            with self.open_file(p) as db_f:
                self.write_xml(
                    tagname="Database",
                    attrs=attrs,
                    indent=4,
                    data=base64.b64encode(db_f.read()),
                    close=True
                )

        self.write_xml("Databases", indent=2, closing=True)

    def write_structure(self):
        structure_path = os.path.join(self.src, STRUCT_JSON)

        if not os.path.exists(structure_path):
            raise Exception("Can't find {}".format(structure_path))

        self.write_xml("Structure", indent=2)

        with self.open_file(structure_path) as struct_file:
            struct_json = json.load(struct_file)

        for obj in struct_json:
            self.write_xml("Object", attrs=obj, data="", close=True, indent=4)

        self.write_xml("Structure", indent=2, closing=True)

    def write_security(self):
        security_path = os.path.join(self.src, "Security")

        if not os.path.exists(security_path):
            raise Exception("Can't find {}".format(security_path))

        self.write_xml("Security", indent=2)

        # groups_path = os.path.join(security_path, "groups.json")
        # if os.path.exists(groups_path)
        #     with self.open_file(groups_path) as f:
        #         groups_json = json.load(f)

        users_path = os.path.join(security_path, USERS_JSON)
        users_json = []

        if os.path.exists(users_path):
            with self.open_file(users_path) as f:
                users_json = json.load(f)

        self.write_xml("Users", indent=4)

        for user in users_json:
            self.write_xml("User", indent=6)

            for key, value in user.items():
                if key == "Rights":
                    self.write_xml("Rights", indent=8)
                    for right in value:
                        self.write_xml(
                            "Right",
                            attrs=right,
                            indent=10,
                            close=True
                        )
                    self.write_xml("Rights", indent=8, closing=True)

                else:
                    self.write_xml(
                        key,
                        data=value,
                        indent=8,
                        close=True,
                        force_cdata=True
                    )

            self.write_xml("User", indent=6, closing=True)

        self.write_xml("Users", indent=4, closing=True)

        ldap_path = os.path.join(security_path, LDAP_LDIF)
        if os.path.exists(ldap_path):
            with self.open_file(ldap_path) as f:
                self.write_xml(
                    "LDAP",
                    indent=4,
                    data=base64.b64encode(f.read()),
                    close=True
                )

        else:
            self.write_xml("LDAP", indent=4, data="", close=True)

        self.write_xml("Security", indent=2, closing=True)

    def write_pages(self):
        pages_path = os.path.join(self.src, "Pages")

        if not os.path.exists(pages_path):
            raise Exception("Can't find {}".format(pages_path))

        self.write_xml("Objects", indent=2)
        for page in os.listdir(pages_path):
            self.walk(pages_path, page, indent=4)
        self.write_xml("Objects", indent=2, closing=True)

        self.write_xml("Actions", indent=2)
        path = os.path.join(pages_path, "Actions-Application")
        if os.path.exists(path):
            self.write_actions(path, 4)
        self.write_xml("Actions", indent=2, closing=True)

    def walk(self, path, name, indent):
        new_path = os.path.join(path, name)
        actions_folder = "Actions-{}".format(name)

        info_path = os.path.join(new_path, INFO_JSON)
        if not os.path.exists(info_path):
            raise Exception("Can't find {}".format(info_path))

        with self.open_file(info_path) as info_file:
            info_json = json.load(info_file)

        self.write_xml("Object", attrs=info_json["attrs"], indent=indent)
        self.write_actions(os.path.join(new_path, actions_folder), indent+2)
        self.write_xml("Objects", indent=indent+2)

        for name in os.listdir(new_path):
            if name in RESERVED_NAMES or name == actions_folder:
                continue

            elif os.path.isdir(os.path.join(new_path, name)):
                self.walk(new_path, name, indent+4)

            else:
                self.write_object(new_path, name, indent+4)

        self.write_xml("Objects", indent=indent+2, closing=True)
        self.write_attributes(info_json["attributes"], indent+2)
        self.write_xml("Object", indent=indent, closing=True)

    def write_actions(self, path, indent):
        actions_map_path = os.path.join(path, MAP_JSON)

        if not os.path.exists(actions_map_path):
            raise Exception("Can't find {}".format(actions_map_path))

        with self.open_file(actions_map_path) as actions_map_file:
            actions_map = json.load(actions_map_file)

        self.write_xml("Actions", indent=indent)

        for action_name in os.listdir(path):
            p = os.path.join(path, action_name)
            if not os.path.isfile(p) or action_name in RESERVED_NAMES:
                continue

            attrs = actions_map.get(action_name, None)
            if not attrs:
                attrs = {
                    "Top": "",
                    "State": "",
                    "Left": "",
                    "ID": str(uuid()),
                    "Name": action_name.split(".")[0],
                }

            with self.open_file(p) as action_f:
                self.write_xml(
                    tagname="Action",
                    attrs=attrs,
                    indent=indent+2,
                    data=action_f.read(),
                    close=True,
                    force_cdata=True
                )

        self.write_xml("Actions", indent=indent, closing=True)

    def write_object(self, path, name, indent):
        with self.open_file(os.path.join(path, name)) as obj_file:
            obj_json = json.load(obj_file)

        self.write_xml("Object", attrs=obj_json["attrs"], indent=indent)
        self.write_xml("Actions", indent=indent+2, data="", close=True)
        self.write_xml("Objects", indent=indent+2, data="", close=True)
        self.write_attributes(obj_json["attributes"], indent+2)
        self.write_xml("Object", indent=indent, closing=True)

    def write_attributes(self, attributes, indent):
        self.write_xml("Attributes", indent=indent)
        for key, value in attributes.items():
            self.write_xml(
                "Attribute",
                attrs={"Name": key},
                data=clear_data(encode(value)),
                indent=indent+2,
                close=True
            )
        self.write_xml("Attributes", indent=indent, closing=True)


def create():
    return Builder().initialize()


if __name__ == "__main__":
    sys.exit(0)
