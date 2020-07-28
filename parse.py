#!/usr/bin/env python
# encoding: utf-8


import argparse
import base64
import cStringIO
import json
import logging
import os
import re
import xml.parsers.expat

from collections import OrderedDict, defaultdict
from modulefinder import ModuleFinder

import constants
from helpers import setup_logging, DEBUG, INFO, ERROR, \
    EXCEPTION, check_python_version, script_exit, \
    create_folder, open_file, json_dump, \
    build_path, clean_data, encode, BLOCK_END, \
    print_block_end, emergency_exit, check_by_regexps, \
    convert_to_regexp, json_load


# UUID regexp pattern
RE_RES_UUID = re.compile("[0-F]{8}-[0-F]{4}-[0-F]{4}-[0-F]{4}-[0-F]{12}", re.I)


# global variable for application parses
PARSER = None


# action file extention (.py or .vb)
ACTION_EXT = ""


# resources GUIDs list
RESOURCES = {}


# libraries list
LIBRARIES = []


# ignore settings
IGNORE = None


def detect_guids(data):
    """Find all UUID in data and update page GUIDs list
    """
    if "current" in PARSER.pages:
        page_id = PARSER.pages["current"]
        PARSER.pages[page_id]["guids"].extend(RE_RES_UUID.findall(data))


def detect_libraries(script_path):
    """Find all libs used by script
    """
    if ACTION_EXT != ".py":
        return

    if "current" not in PARSER.pages:
        return

    page_id = PARSER.pages["current"]

    finder = ModuleFinder()
    try:
        DEBUG("Parsing: %s", script_path)
        finder.run_script(script_path)
        DEBUG("Done: %s", script_path)

    except Exception:
        ERROR("Can't parse script: %s", script_path)
        EXCEPTION("")
        return

    PARSER.pages[page_id]["libraries"].extend(finder.modules.keys())
    PARSER.pages[page_id]["libraries"].extend(finder.badmodules.keys())


def sort_dict(data):
    """Return dictionary sorted by key in lower case
    """
    return OrderedDict(sorted(data.items(), key=lambda pair: pair[0].lower()))


class TagHandler(object):
    """XML Tag handler
    """

    def __init__(self, tagname="", attrs=None):
        self.tagname = tagname
        self.attrs = attrs or {}

        self.is_cdata_section = False

    def start(self, tagname, attrs):
        """On element start
        """
        self.tagname = tagname
        self.attrs = attrs

        self.register()

    def end(self):
        """On element end
        """
        self.unregister()

    def child_start(self, tagname, attrs):
        """Child element start
        """
        pass

    def tag_end(self, tagname):
        """On element or child end
        """
        if tagname == self.tagname:
            self.end()

        else:
            self.child_end(tagname)

    def child_end(self, tagname):
        """Child element end
        """
        pass

    def child_data(self, data):
        """On element data
        """
        pass

    def start_cdata(self):
        """On CDATA section start
        """
        self.is_cdata_section = True

    def end_cdata(self):
        """On CDATA section end
        """
        self.is_cdata_section = False

    @property
    def parent(self):
        """Returns element parent TagHandler object
        """
        return PARSER.tag_handlers[-2]

    def register(self):
        """Add tag handler to stack
        """
        PARSER.add_tag_handler_to_stack(self)
        return self

    def unregister(self):
        """Remove tag handler from stack
        """
        PARSER.remove_tag_handler_from_stack()
        return self

    def __str__(self):
        return "<%s>" % self.tagname


class RootHandler(TagHandler):
    """Root tag handler
    """

    def child_start(self, tagname, attrs):
        """Waiting for child with Application tagname and initialize it
        """
        if tagname == "Application":
            attrs["Name"] = "Application"
            return ApplicationTagHandler().start(tagname, attrs)

    @property
    def parent(self):
        """Root handler hasn't parent -> return none
        """
        return None

    def __str__(self):
        return "<root>"


class InformationTagHandler(TagHandler):
    """Information tag TagHandler
    """

    def __init__(self, *args, **kwargs):
        super(InformationTagHandler, self).__init__(*args, **kwargs)

        self.data = defaultdict(list)
        self.current_tag = ""

    def child_start(self, tagname, attrs):
        self.current_tag = tagname
        self.data[self.current_tag].append('')

    def child_data(self, data):
        if self.current_tag:
            self.data[self.current_tag].append(data)

    def child_end(self, tagname):
        if tagname == self.current_tag:
            self.current_tag = ""

    @print_block_end
    def end(self):
        global ACTION_EXT

        # remove unnecessary symbols from data and encode it
        for key, value in self.data.items():
            self.data[key] = encode(clean_data("".join(value)))

        # detect application programming language
        ACTION_EXT = {
            "python": ".py",
            "vscript": ".vb"
        }.get(self.data["ScriptingLanguage"].lower(), "python")

        INFO("Sripts extention will be '*%s'", ACTION_EXT)
        INFO("Completed: Application Information")

        self.save()
        super(InformationTagHandler, self).end()

    def start(self, tagname, attrs):
        super(InformationTagHandler, self).start(tagname, attrs)
        INFO("Parsing: Application Information")

    def save(self):
        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["info"]):

            return

        PARSER.write_json_file(
            constants.INFO_FILE,
            sort_dict(self.data)
        )


class BaseDRTagHandler(TagHandler):

    FOLDER = ""
    TAG = ""

    def __init__(self, *args, **kwargs):
        super(BaseDRTagHandler, self).__init__(*args, **kwargs)

        self.current = None
        PARSER.append_to_current_path(self.FOLDER)


    def create_name(self, attrs):
        return attrs["Name"]

    def save_file(self):
        pass

    def create_new_file_handler(self, name):
        raise NotImplementedError

    def child_start(self, tagname, attrs):
        if tagname == self.TAG:

            name = self.create_name(attrs)
            if not name:
                return

            self.current = {
                "name": name
            }

            self.current["file"] = self.create_new_file_handler(
                self.current["name"]
            )

    def child_data(self, data):
        if self.current:
            self.current["file"].write(encode(data))

    def child_end(self, tagname):
        if tagname == self.TAG and self.current:
            self.save_file()
            self.current = None

    @print_block_end
    def end(self):
        PARSER.pop_from_current_path()
        super(BaseDRTagHandler, self).end()


class LibrariesTagHandler(BaseDRTagHandler):

    FOLDER = constants.LIBRARIES_FOLDER
    TAG = "Library"

    def create_name(self, attrs):
        LIBRARIES.append(attrs["Name"])

        if not check_by_regexps(attrs["Name"], IGNORE["Libraries"]):
            return "{}{}".format(attrs["Name"], ACTION_EXT)

        else:
            DEBUG("Ignore library: %s", attrs["Name"])
            return ""

    def child_data(self, data):
        if not self.is_cdata_section:
            return

        super(LibrariesTagHandler, self).child_data(data)

    def save_file(self):
        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["libraries"]):

            return

        # add new line at the end
        data = self.current["file"].getvalue()
        data += '\n' if data and data[-1] != '\n' else ''

        PARSER.write_file(
            self.current["name"],
            data
        )

    def save_map(self):
        pass

    def create_new_file_handler(self, name):
        return cStringIO.StringIO()

    def end(self):
        INFO("Completed: Libraries")
        super(LibrariesTagHandler, self).end()
        self.update_pages_libraries()

    def start(self, tagname, attrs):
        super(LibrariesTagHandler, self).start(tagname, attrs)
        INFO("Parsing: Libraries")

    @print_block_end
    def update_pages_libraries(self):

        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["pages"]):

            return

        INFO("Parsing: used libraries for every page")

        PARSER.append_to_current_path(constants.PAGES_FOLDER)

        libraries_set = set(LIBRARIES)

        for page in PARSER.pages.values():

            libs = list(libraries_set & set(page["libraries"]))

            PARSER.append_to_current_path(page["name"])

            PARSER.write_json_file(
                constants.LIBRARIES_FILE,
                sorted(libs, key=lambda x: x.lower())
            )

            PARSER.pop_from_current_path()

        PARSER.pop_from_current_path()
        INFO("Completed: used libraries for every page")


class ResourcesTagHandler(BaseDRTagHandler):

    FOLDER = constants.RESOURCES_FOLDER
    TAG = "Resource"

    def create_name(self, attrs):
        RESOURCES[attrs["ID"]] = name = "{}_{}_{}".format(
            attrs["ID"],
            attrs["Type"] or "res",
            attrs["Name"]
        )

        if not check_by_regexps(attrs["Name"], IGNORE["Resources"]):
            return name

        else:
            DEBUG("Ignore resource: %s", attrs["Name"])
            return ""

    def save_file(self):
        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["resources"]):

            return

        PARSER.write_file(
            self.current["name"],
            base64.b64decode(self.current["file"].getvalue())
        )

    def create_new_file_handler(self, name):
        return cStringIO.StringIO()

    def end(self):
        INFO("Completed: Resources")
        super(ResourcesTagHandler, self).end()
        self.update_pages_resources()

    def start(self, tagname, attrs):
        super(ResourcesTagHandler, self).start(tagname, attrs)
        INFO("Parsing: Resources")

    @print_block_end
    def update_pages_resources(self):

        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["pages"]):

            return

        INFO("Parsing: used resources for every page")

        PARSER.append_to_current_path(constants.PAGES_FOLDER)

        resources_set = set(RESOURCES.keys())

        for page in PARSER.pages.values():

            keys = list(resources_set & set(page["guids"]))

            PARSER.append_to_current_path(page["name"])

            PARSER.write_json_file(
                constants.RESOURCES_FILE,
                sorted(
                    [RESOURCES[key] for key in keys],
                    key=lambda x: x.lower()
                )
            )

            PARSER.pop_from_current_path()

        PARSER.pop_from_current_path()
        INFO("Completed: used resources for every page")


class DatabasesTagHandler(BaseDRTagHandler):

    FOLDER = constants.DATABASES_FOLDER
    TAG = "Database"

    def create_name(self, attrs):
        if not check_by_regexps(attrs["Name"], IGNORE["Databases"]):
            return "{}_{}.{}".format(attrs["ID"], attrs["Name"], attrs["Type"])

        else:
            DEBUG("Ignore database: %s", attrs["Name"])
            return ""

    def save_file(self):
        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["databases"]):

            return

        PARSER.write_file(
            self.current["name"],
            base64.b64decode(self.current["file"].getvalue())
        )

    def create_new_file_handler(self, name):
        return cStringIO.StringIO()

    def end(self):
        INFO("Completed: Databases")
        super(DatabasesTagHandler, self).end()

    def start(self, tagname, attrs):
        super(DatabasesTagHandler, self).start(tagname, attrs)
        INFO("Parsing: Databases")


class DummyObjectTagHandler(TagHandler):

    def child_start(self, tagname, attrs):
        if tagname == "Object":
            DummyObjectTagHandler().start(tagname, attrs)


class PagesTagHandler(TagHandler):

    FOLDER = constants.PAGES_FOLDER

    def __init__(self, *args, **kwargs):
        super(PagesTagHandler, self).__init__(*args, **kwargs)
        PARSER.append_to_current_path(self.FOLDER)

    def child_start(self, tagname, attrs):
        if tagname == "Object":

            cls = DummyObjectTagHandler
            if PARSER.config["parse_all"] or \
                    PARSER.config["parse"]["pages"]:

                if not check_by_regexps(attrs["Name"], IGNORE["Pages"]):
                    cls = PageTagHandler

                    PARSER.pages[attrs["ID"]] = {
                        "id": attrs["ID"],
                        "name": attrs["Name"],
                        "events": [],
                        "actions": {},
                        "guids": [],
                        "libraries": []
                    }
                    PARSER.pages["current"] = attrs["ID"]

                else:
                    DEBUG("Ignore page: %s", attrs["Name"])

            cls(tagname, attrs).register()

    @print_block_end
    def end(self):
        super(PagesTagHandler, self).end()
        PARSER.pop_from_current_path()
        INFO("Completed: Pages")

        if "current" in PARSER.pages:
            del PARSER.pages["current"]

    def start(self, tagname, attrs):
        super(PagesTagHandler, self).start(tagname, attrs)
        INFO("Parsing: Pages")


class ActionsTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(ActionsTagHandler, self).__init__(*args, **kwargs)

        self.actions_map = {}
        self.current_action = None
        self.has_actions = False

    def create_base_dir(self):
        self.parent.create_dir()

        PARSER.append_to_current_path(
            "Actions-{}".format(self.parent.attrs["Name"])
        )
        try:
            PARSER.create_folder_from_current_path()

        except OSError:
            ERROR("Folder already exists: %s",
                  build_path(PARSER.current_path()))

    def child_start(self, tagname, attrs):
        if tagname == "Action":

            if not self.has_actions:
                self.create_base_dir()
                self.has_actions = True

            if self.parent.tagname.lower() == "application":
                name = "{}_{}{}".format(attrs["ID"], attrs["Name"], ACTION_EXT)

            else:
                name = "{}{}".format(attrs["Name"], ACTION_EXT)

            self.current_action = {
                "file": cStringIO.StringIO(),
                "name": name,
                "attrs": sort_dict(attrs)
            }

    def child_data(self, data):
        if not self.is_cdata_section:
            return

        if self.current_action:
            self.current_action["file"].write(encode(data))

    def end(self):
        if self.parent.tagname == "Application" and not self.has_actions:
            self.create_base_dir()
            self.has_actions = True
        
        if self.has_actions:
            self.save_actions_map()
            PARSER.pop_from_current_path()

        self.parent.is_actions_found = self.has_actions

        super(ActionsTagHandler, self).end()

    def child_end(self, tagname):
        if tagname == "Action":
            self.save_action()
            self.current_action = None

    def save_action(self):
        data = self.current_action["file"].getvalue()
        detect_guids(data)

        # add new line at end of file
        data += '\n' if data and data[-1] != '\n' else ''

        PARSER.write_file(
            self.current_action["name"],
            data
        )

        self.actions_map[self.current_action["name"]] = \
            self.current_action["attrs"]

        action_path = os.path.join(PARSER.current_path(),
                                   self.current_action["name"])

        detect_libraries(action_path)

    def save_actions_map(self):
        PARSER.write_json_file(
            constants.MAP_FILE,
            sort_dict(self.actions_map)
        )


class ObjectTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(ObjectTagHandler, self).__init__(*args, **kwargs)

        self.is_actions_found = False
        self.attributes = defaultdict(list)
        self.current_attribute = None
        self.has_folder = False
        self.childs_order = []

    def create_dir(self):
        if not self.has_folder:
            PARSER.append_to_current_path(self.attrs["Name"])
            PARSER.create_folder_from_current_path()
            self.has_folder = True

    def child_start(self, tagname, attrs):
        if tagname == "Attribute":
            self.current_attribute = attrs["Name"]
            self.attributes[self.current_attribute].append('')

        elif tagname == "Object":
            if not self.has_folder:
                self.create_dir()

            self.childs_order.append(attrs["Name"])

            ObjectTagHandler().start(tagname, attrs)

        elif tagname == "Actions":
            ActionsTagHandler().start(tagname, attrs)

    def child_data(self, data):
        if self.current_attribute:
            self.attributes[self.current_attribute].append(data)

    def child_end(self, tagname):
        if tagname == "Attribute":
            self.current_attribute = None

    def end(self):
        super(ObjectTagHandler, self).end()
        self.save()

    def save(self):
        if self.has_folder or self.is_actions_found:
            name = constants.INFO_FILE
        else:
            name = "{}.json".format(self.attrs["Name"])

        if "Type" in self.attrs \
            and self.attrs['Type'] in constants.EXTERNAL_SOURCE_TYPES \
            and "source" in self.attributes:
                source_name = name + constants.EXTERNAL_SOURCE_TYPES[self.attrs['Type']]
                PARSER.write_file(source_name, "".join(self.attributes["source"]))
                self.attrs["source_file_name"] = source_name
                del self.attributes["source"]

        self.attributes = {
            key: encode(clean_data("".join(val))).split('\n')
            for (key, val) in self.attributes.items()
        }

        data = OrderedDict([
            ("attrs", sort_dict(self.attrs)),
            ("attributes", sort_dict(self.attributes))
        ])

        data = json.dumps(data, indent=4)
        detect_guids(data)

        PARSER.write_file(name, data)

        if self.childs_order:
            order_data = json.dumps(self.childs_order, indent=4)
            detect_guids(order_data)
            PARSER.write_file(constants.CHILDS_ORDER, order_data)

        if self.has_folder or self.is_actions_found:
            PARSER.pop_from_current_path()


class PageTagHandler(ObjectTagHandler):

    def end(self):
        super(PageTagHandler, self).end()
        INFO("Page '%s' saved!", self.attrs["Name"])


class E2vdomTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(E2vdomTagHandler, self).__init__(*args, **kwargs)
        self.current_mode = ""
        self.current_node = None
        self.is_data_allowed = False
        self.actions = {}

    def start(self, tagname, attrs):
        super(E2vdomTagHandler, self).start(tagname, attrs)
        INFO("Parsing: E2VDOM")

    @print_block_end
    def end(self):
        super(E2vdomTagHandler, self).end()

        for page in PARSER.pages.values():
            for act_id in page["actions"]:
                page["actions"][act_id] = self.actions.get(act_id, '')

        self.save()
        INFO("Completed: E2VDOM")

    def child_start(self, tagname, attrs):
        if tagname in ("Events", "Actions"):
            self.current_mode = tagname

        if self.current_mode == "Events" and tagname in ("Event", "Action"):
            if tagname == "Event":
                self.current_node = attrs
                self.current_node["actions"] = []

            elif tagname == "Action":
                self.current_node["actions"].append(attrs["ID"])

        elif self.current_mode == "Actions" and tagname in ("Action", "Parameter"):

            if tagname == "Action":
                self.current_node = attrs
                self.current_node["Params"] = []

            elif tagname == "Parameter":
                key = "ScriptName" if "ScriptName" in attrs else "Name"
                self.current_node["Params"].append([attrs[key], []])
                self.is_data_allowed = True

    def child_data(self, data):
        if self.is_data_allowed:
            self.current_node["Params"][-1][1].append(encode(data))

    def child_end(self, tagname):

        if self.current_mode == "Events" and tagname == "Event":
            page = PARSER.pages.get(self.current_node["ContainerID"], "")

            if page:
                page["events"].append(sort_dict(self.current_node))
                for action in self.current_node["actions"]:
                    if not page["actions"].get(action, ""):
                        page["actions"][action] = ""

            self.current_node = ""

        elif self.current_mode == "Events" and tagname == "Events":
            self.current_mode = ""

        elif self.current_mode == "Actions" and tagname == "Action":
            if not self.current_node["Params"]:
                del self.current_node["Params"]

            self.actions[self.current_node["ID"]] = sort_dict(self.current_node)
            self.current_node = ""

        elif self.current_mode == "Actions" and tagname == "Actions":
            self.current_mode = ""

        elif self.current_mode == "Actions" and tagname == "Parameter":
            self.is_data_allowed = False
            self.current_node["Params"][-1][1] = \
                clean_data("".join(self.current_node["Params"][-1][1]))

    def save(self):

        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["e2vdom"]):

            return

        PARSER.append_to_current_path(constants.PAGES_FOLDER)

        for page in PARSER.pages.values():
            PARSER.pages["current"] = page["id"]

            #FILTER FROM EMPTY VALUES
            FILTERED_ACTIONS = { k:v  for k, v in page["actions"].items() if v }
            SORTED_ACTIONS = OrderedDict(sorted(FILTERED_ACTIONS.items()))
            
            #POP "ID" KEY AND CONVERT TO LIST
            SORTED_ARRAY_ACTIONS = [action[1] for action in SORTED_ACTIONS.items()]

            EVENTS = page["events"]
            SORTED_EVENTS = sorted(EVENTS, key=lambda x: x["ContainerID"])

            data = json.dumps(
                OrderedDict([
                    ("actions", SORTED_ARRAY_ACTIONS),
                    ("events", SORTED_EVENTS),
                ]),
                indent=4
            )

            detect_guids(data)

            PARSER.append_to_current_path(page["name"])
            PARSER.write_file(
                constants.E2VDOM_FILE,
                data
            )

            PARSER.pop_from_current_path()

        PARSER.pop_from_current_path()

        if "current" in PARSER.pages:
            del PARSER.pages["current"]


class SecurityTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(SecurityTagHandler, self).__init__(*args, **kwargs)

        self.groups_and_users = OrderedDict([
            ("groups", []),
            ("users", [])
        ])

        self.current_mode = ""
        self.current_node = None
        self.is_data_allowed = False
        self.ldapf = None

        PARSER.append_to_current_path(constants.SECURITY_FOLDER)

    def start(self, tagname, attrs):
        super(SecurityTagHandler, self).start(tagname, attrs)
        INFO("Parsing: Security")

    @print_block_end
    def end(self):
        super(SecurityTagHandler, self).end()
        self.save()
        INFO("Completed: Security")

    def child_start(self, tagname, attrs):
        if tagname in ("Groups", "Users", "LDAP"):
            self.current_mode = tagname

        if self.current_mode == "Users":
            if tagname == "User":
                self.current_node = []

            elif tagname in ("Login", "Password", "FirstName",
                             "LastName", "Email", "SecurityLevel",
                             "MemberOf"):

                self.current_node.append([tagname, []])
                self.is_data_allowed = True

            elif tagname == "Rights":
                self.current_node.append([tagname, []])

            elif tagname == "Right":
                self.current_node[-1][1].append(sort_dict(attrs))

        elif self.current_mode == "LDAP":
            self.ldapf = cStringIO.StringIO()
            self.is_data_allowed = True

        elif self.current_mode == "Groups":
            ERROR("Group are unsupported")

    def child_data(self, data):
        if self.is_data_allowed:
            if self.current_mode == "Users":
                self.current_node[-1][1].append(encode(data))

            elif self.current_mode == "LDAP":
                self.ldapf.write(data)

            elif self.current_mode == "Groups":
                ERROR("Group are unsupported")

    def child_end(self, tagname):
        if self.current_mode == "Users":
            if tagname == "Users":
                self.current_mode = ""
                self.current_node = None

            elif tagname == "User":

                user = dict(self.current_node)
                if user.get("Rights", None):
                    user["Rights"].sort(key=lambda right: right["Target"])

                else:
                    del user["Rights"]

                self.groups_and_users["users"].append(sort_dict(user))

            elif tagname in ("Login", "Password", "FirstName",
                             "LastName", "Email", "SecurityLevel",
                             "MemberOf"):

                self.is_data_allowed = False
                self.current_node[-1][1] = "".join(self.current_node[-1][1])

        elif self.current_mode == "Groups":
            ERROR("Group are unsupported")

    def save(self):

        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["security"]):

            return

        self.groups_and_users["users"].sort(key=lambda user: user["Login"])

        PARSER.write_json_file(
            constants.USERS_GROUPS_FILE,
            self.groups_and_users
        )

        if self.ldapf:
            PARSER.write_file(
                constants.LDAP_LDIF,
                base64.b64decode(self.ldapf.getvalue())
            )


class StructureTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(StructureTagHandler, self).__init__(*args, **kwargs)
        self.structure = []

    def start(self, tagname, attrs):
        super(StructureTagHandler, self).start(tagname, attrs)
        INFO("Parsing: Structure")

    @print_block_end
    def end(self):
        super(StructureTagHandler, self).end()
        # self.save()
        INFO("Completed: Structure")

    def child_start(self, tagname, attrs):
        if tagname == "Object":
            self.structure.append(sort_dict(attrs))

    def save(self):
        if not (PARSER.config["parse_all"] or
                PARSER.config["parse"]["structure"]):

            return

        PARSER.write_json_file(constants.STRUCT_FILE, self.structure)


class ApplicationTagHandler(TagHandler):

    def create_dir(self):
        pass

    def child_start(self, tagname, attrs):
        tag_handlers_map = {
            "information": InformationTagHandler,
            "libraries": LibrariesTagHandler,
            "resources": ResourcesTagHandler,
            "databases": DatabasesTagHandler,
            "objects": PagesTagHandler,
            "e2vdom": E2vdomTagHandler,
            "structure": StructureTagHandler,
            "security": SecurityTagHandler,
        }

        if PARSER.config["parse_all"] or PARSER.config["parse"]["app_actions"]:

            tag_handlers_map["actions"] = ActionsTagHandler

        handler_cls = tag_handlers_map.get(tagname.lower(), None)
        if handler_cls:
            handler_cls().start(tagname, attrs)

        else:
            DEBUG("%s found unhandled tag '%s'", self.tagname, tagname)


class Parser(object):
    """VDOM Application XML parser class
    """

    def __init__(self):
        self.config = None
        self.target_folder = None
        self._handlers_stack = []
        self._current_path = []
        self.pages = {}

    def create_folder_from_current_path(self):
        """Create folder using current path
        """
        os.makedirs(self.current_path())

    def current_path(self):
        """Return current path string
        """
        return build_path(*self._current_path)

    def append_to_current_path(self, path):
        """Append new path to current
        """
        self._current_path.append(path)

    def pop_from_current_path(self):
        """Go to higher level in
        """
        return self._current_path.pop()

    def write_file(self, name, data):
        """Write data to file
        """
        path = build_path(self.current_path(), name)

        DEBUG("Writing data to %s", path)

        with open_file(path, "wb") as hdlr:
            hdlr.write(data)

    def write_json_file(self, name, data):
        """Convert data to JSON and
            write it to file
        """
        path = build_path(self.current_path(), name)

        DEBUG("Writing JSON data to %s", path)

        with open_file(path, "wb") as hdlr:
            json_dump(data, hdlr, critical=True)

    @property
    def current_handler(self):
        """Return tag handler which is active
        """
        return self.tag_handlers[-1]

    @property
    def tag_handlers(self):
        """Return tag handlers stack
        """
        return self._handlers_stack

    def add_tag_handler_to_stack(self, handler):
        """Add tag handler to stack
        """
        self.tag_handlers.append(handler)

    def remove_tag_handler_from_stack(self):
        """Remove tag handler from stack
        """
        self.tag_handlers.pop()

    def start_element(self, tagname, attrs):
        """New element found
        """
        self.current_handler.child_start(tagname, attrs)

    def end_element(self, tagname):
        """Element closed
        """
        self.current_handler.tag_end(tagname)

    def char_data(self, data):
        """Element data
        """
        self.current_handler.child_data(data)

    def start_cdata(self):
        """CDATA section found
        """
        self.current_handler.start_cdata()

    def end_cdata(self):
        """CDATA section closed
        """
        self.current_handler.end_cdata()

    def parse(self, source, target, config):
        """Setup logging and start main process
        """
        self.config = config
        self.target_folder = target
        self.append_to_current_path(self.target_folder)

        RootHandler().register()

        expat = xml.parsers.expat.ParserCreate()
        expat.StartElementHandler = self.start_element
        expat.EndElementHandler = self.end_element
        expat.CharacterDataHandler = self.char_data
        expat.StartCdataSectionHandler = self.start_cdata
        expat.EndCdataSectionHandler = self.end_cdata

        expat.ParseFile(source)


@print_block_end
def create_basic_structure(config):
    """Create basic folders
    """
    DEBUG("Creating basic structure")

    root = config["target"]["path"] = create_folder(**config["target"])

    if config["parse_all"]:
        for folder in constants.BASE_FOLDERS:
            create_folder(os.path.join(root, folder))

    else:
        if config["parse"]["databases"]:
            create_folder(os.path.join(root, constants.DATABASES_FOLDER))

        if config["parse"]["libraries"]:
            create_folder(os.path.join(root, constants.LIBRARIES_FOLDER))

        if config["parse"]["pages"]:
            create_folder(os.path.join(root, constants.PAGES_FOLDER))

        if config["parse"]["resources"]:
            create_folder(os.path.join(root, constants.RESOURCES_FOLDER))

        if config["parse"]["security"]:
            create_folder(os.path.join(root, constants.SECURITY_FOLDER))

        if config["parse"]["app_actions"]:
            create_folder(os.path.join(root, constants.APP_ACTIONS_FOLDER))

    INFO("Basic structure successfully created")


def parse_app(config):
    """VDOM Application XML parser initialization
        and start parsing process
    """
    global PARSER

    DEBUG("Initialize VDOM Application XML parser")
    PARSER = Parser()

    INFO("Parsing started...")
    PARSER.parse(config["source"], config["target"]["path"], config)

    INFO("Completed!")


def parse_ignore_file(config):
    """Convert strings to regexps
    """
    global IGNORE

    if not config["ignore"]:
        config["ignore"] = {}

    if not isinstance(config["ignore"], dict):
        ERROR("Ignore settings must be dict")
        emergency_exit()

    keys = ["Resources", "Libraries",
            "Databases", "Actions", "Pages"]

    for key in keys:
        data = config["ignore"].get(key, [])
        if not isinstance(data, (list, tuple)):
            data = (data,)

        config["ignore"][key] = convert_to_regexp(data)

    IGNORE = config["ignore"]


def parse(config):
    """Call copy functions in cycle
    """
    parse_ignore_file(config)
    create_basic_structure(config)
    parse_app(config)


def main():
    """Main function
    """
    args_parser = argparse.ArgumentParser()

    args_parser.add_argument("source", type=argparse.FileType("rb"),
                             help="application XML file")

    args_parser.add_argument("-t", "--target", type=str,
                             help="target folder")

    args_parser.add_argument("-v", "--verbosity", action="count",
                             help="be more verbose",
                             default=0)

    args_parser.add_argument("-e", "--erase", action="store_true",
                             help="erase target folder")

    args_parser.add_argument("-q", "--quiet", action="store_true",
                             help="no user interaction")

    args_parser.add_argument("-i", "--ignore-cfg",
                             type=argparse.FileType("rb"),
                             help="ignore config file")

    args_parser.add_argument("-l", "--libraries",
                             action="store_true",
                             help="parse libraries")

    args_parser.add_argument("-p", "--pages",
                             action="store_true",
                             help="parse pages")

    args_parser.add_argument("-d", "--databases",
                             action="store_true",
                             help="parse databases")

    args_parser.add_argument("-r", "--resources",
                             action="store_true",
                             help="parse resources")

    args_parser.add_argument("-n", "--info",
                             action="store_true",
                             help="parse information")

    args_parser.add_argument("-s", "--security",
                             action="store_true",
                             help="parse security")

    args_parser.add_argument("-u", "--structure",
                             action="store_true",
                             help="parse structure")

    args_parser.add_argument("-o", "--e2vdom",
                             action="store_true",
                             help="parse e2vdom")

    args_parser.add_argument("-c", "--app-actions",
                             action="store_true",
                             help="parse application actions")

    args_parser.add_argument("-ds", "--delete-source",
                             action="store_true",
                             help="delete source .xml file")

    args = args_parser.parse_args()

    # Setup logging system and show necessary messages
    log_level = logging.INFO if not args.verbosity else logging.DEBUG
    show_module_name = args.verbosity > 1

    setup_logging(log_level, module_name=show_module_name)

    INFO("")
    INFO("Information logging turned on")
    DEBUG("Debug logging turned on")
    INFO("")
    INFO(BLOCK_END)
    INFO("")

    ignore = args.ignore_cfg
    if ignore:
        INFO("Parsing: 'ignore' configuration file")
        ignore = json_load(ignore, critical=True)
        INFO("Done: 'ignore' configuration file")

    config = {
        "target": {
            "path": args.target or os.path.split(args.source.name)[-1].split(".")[0],
            "erase": args.erase,
            "quiet": args.quiet,
        },
        "source": args.source,
        "ignore": ignore,
        "delete_source": args.delete_source,
        "parse": {
            "app_actions": args.app_actions,
            "e2vdom": args.e2vdom,
            "structure": args.structure,
            "security": args.security,
            "info": args.info,
            "resources": args.resources,
            "databases": args.databases,
            "pages": args.pages,
            "libraries": args.libraries
        },
    }

    parse_all = False
    for val in config["parse"].values():
        parse_all = parse_all or val

    config["parse_all"] = not parse_all

    # Main process starting
    parse(config)

    if config["delete_source"] and os.path.exists(args.source.name):
        args.source.close()
        os.remove(args.source.name)

    INFO("\nPath to application:\n{}".format(config["target"]["path"]))


if __name__ == "__main__":
    check_python_version()
    main()
    script_exit()
