#!/usr/bin/python
#encoding: utf-8

import base64
import collections
import cStringIO
import json
import logging
import os
import sys
import xml

__version__ = "0.0.1"



# Logging
INFO = None
DEBUG = None

JSON_INDENT = 4


INFO_JSON = "__info__.json"
E2VDOM_JSON = "__e2vdom__.json"
MAP_JSON = "__map__.json"
USERS_JSON = "__users__.json"
GROUPS_JSON = "__groups__.json"
STRUCT_JSON = "__struct__.json"
LDAP_LDIF = "__ldap__.ldif"

RESERVED_NAMES = (
    INFO_JSON,
    E2VDOM_JSON,
    MAP_JSON,
    USERS_JSON,
    GROUPS_JSON,
    LDAP_LDIF
)


def encode(data):
    return data.encode("utf-8")


def build_path(*args):
    return os.path.join(*args)


empty_string = set(["\n", "\t"])
def clear_data(data):
    if len(set(data) - empty_string) > 0:
        return data
    else:
        return ""

def setup_logging(debug=False):
    """Setup logging
    """
    global DEBUG, INFO

    debug_level = logging.DEBUG if debug else logging.INFO

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(debug_level)
    ch.setFormatter(logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s'))

    root = logging.getLogger()
    root.setLevel(debug_level)
    root.addHandler(ch)

    DEBUG = root.debug
    INFO = root.info


def create_dir(name):
    """If folder @name exists then create another new
    """
    app_path = name
    if os.path.exists(app_path):

        i = 0
        while os.path.exists("{0}{1}".format(app_path, i)):
            i += 1

        app_path = "{0}{1}".format(app_path, i)

    os.mkdir(app_path)
    return app_path



class TagHandler(object):

    def __init__(self, tagname, attrs):
        self.tagname = tagname
        self.attrs = attrs

    def child_start(self, tagname, attrs):
        pass

    def child_end(self, tagname):
        pass

    def child_data(self, data):
        pass

    @property
    def parent(self):
        return Parser().tag_handlers[-2]

    def register(self):
        """Add tag handler to stack
        """
        Parser().add_tag_handler_to_stack(self)
        return self

    def unregister(self):
        """Remove tag handler from stack
        """
        Parser().remove_tag_handler_from_stack(self)
        return self

    def __str__(self):
        return self.tagname


class RootHandler(TagHandler):

    def __init__(self):
        pass

    def child_start(self, tagname, attrs):
        if tagname == "Application":
            attrs["Name"] = "Application"
            return ApplicationTagHandler(tagname, attrs).register()

    @property
    def parent(self):
        return None

    def __str__(self):
        return "Root"


class InformationTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(InformationTagHandler, self).__init__(*args, **kwargs)

        self.data = collections.defaultdict(list)
        self.current_tag = ""

    def child_start(self, tagname, attrs):
        self.current_tag = tagname
    
    def child_data(self, data, depth=0):
        if self.current_tag:
            self.data[self.current_tag].append(encode(data))
        
    def child_end(self, tagname, depth=0):
        if tagname != "Information":
            self.current_tag = ""

        else:
            self.data = {k: "".join(v) for k,v in self.data.items()}
            self.save()            
            self.unregister()


    def save(self):
        Parser().write_file(INFO_JSON, json.dumps(self.data, indent=JSON_INDENT))


class BaseDRTagHandler(TagHandler):

    FOLDER = ""
    TAG = ""

    def __init__(self, *args, **kwargs):
        super(BaseDRTagHandler, self).__init__(*args, **kwargs)

        self.current = None
        self.count = 0
        self.map = {}

        self.create_base_dir()

        # INFO("Starting parse <{}s>".format(self.TAG))

    def create_base_dir(self):
        Parser().append_to_current_path(self.FOLDER)
        Parser().create_folder_from_current_path()

    def create_name(self, attrs):
        return attrs["Name"]

    def create_attrs(self, attrs):
        return attrs

    def save_file(self):
        pass

    def save_map(self):
        pass

    def create_new_file_handler(self, name):
        raise NotImplementedError

    def child_start(self, tagname, attrs):
        if tagname == self.TAG:
            self.count += 1

            self.current = {
                "name": self.create_name(attrs),
                "attrs": self.create_attrs(attrs)
            }

            self.current["file"] = self.create_new_file_handler(self.current["name"])

    def child_data(self, data):
        if self.current:
            self.current["file"].write(encode(data))

    def child_end(self, tagname):
        if tagname == self.TAG:
            self.save_file()
            self.map[self.current["name"]] = self.current["attrs"]
            self.current = None

        else:
            self.save_map()
            self.unregister()

            Parser().pop_from_current_path()


class LibrariesTagHandler(BaseDRTagHandler):

    FOLDER = "Libraries"
    TAG = "Library"
    
    def create_name(self, attrs):
        return "{}.py".format(attrs["Name"])

    def create_attrs(self, attrs):
        return attrs

    def save_file(self):
        Parser().write_file(self.current["name"], self.current["file"].getvalue())

    def save_map(self):
        pass

    def create_new_file_handler(self, name):
        return cStringIO.StringIO()


class ResourcesTagHandler(BaseDRTagHandler):

    FOLDER = "Resources"
    TAG = "Resource"
    
    def create_name(self, attrs):
        return attrs["Name"]

    def create_attrs(self, attrs):
        return attrs

    def save_file(self):
        Parser().write_file(self.current["name"], base64.b64decode(self.current["file"].getvalue()))

    def save_map(self):
        Parser().write_file(MAP_JSON, json.dumps(self.map, indent=JSON_INDENT))

    def create_new_file_handler(self, name):
        return cStringIO.StringIO()


class DatabasesTagHandler(ResourcesTagHandler):

    FOLDER = "Databases"
    TAG = "Database"
    
    def create_name(self, attrs):
        return "{}.{}".format(attrs["Name"], attrs["Type"])


class PagesTagHandler(TagHandler):

    FOLDER = "Pages"

    def __init__(self, *args, **kwargs):
        super(PagesTagHandler, self).__init__(*args, **kwargs)
        self.create_base_dir()

    def create_base_dir(self):
        Parser().append_to_current_path(self.FOLDER)
        Parser().create_folder_from_current_path()

    def child_start(self, tagname, attrs):
        if tagname == "Object":
            ObjectTagHandler(tagname, attrs).register()
            Parser().pages[attrs["ID"]] = {
                "name": attrs["Name"],
                "events": [],
                "actions": {}
            }

    def child_end(self, tagname):
        if tagname == "Objects":
            self.unregister()
            Parser().pop_from_current_path()


class ActionsTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(ActionsTagHandler, self).__init__(*args, **kwargs)

        self.count = 0
        self.current_action = None
        self.actions_map = {}

        DEBUG("Started parsing actions")

    def create_base_dir(self):
        self.parent.create_dir()

        Parser().append_to_current_path("Actions-{}".format(self.parent.attrs["Name"]))
        Parser().create_folder_from_current_path()

        DEBUG("Folder created - {}".format(Parser().current_path()))
        
    def child_start(self, tagname, attrs):
        if tagname == "Action":
            if not self.count:
                self.create_base_dir()

            self.current_action = {
                "file": cStringIO.StringIO(),
                "name": "{}.py".format(attrs["Name"]),
                "attrs": attrs
            }

            self.count += 1

    def child_data(self, data):
        if self.current_action:
            self.current_action["file"].write(encode(data))

    def child_end(self, tagname):
        if tagname == "Action":
            self.save_action()
            self.current_action = None

        elif tagname == "Actions":
            if self.count:
                self.save_actions_map()
                Parser().pop_from_current_path()

            self.parent.actions_found = self.count
            self.unregister()

    def save_action(self):
        Parser().write_file(self.current_action["name"], self.current_action["file"].getvalue())
        self.actions_map[self.current_action["name"]] = self.current_action["attrs"]

    def save_actions_map(self):
        Parser().write_file(MAP_JSON, json.dumps(self.actions_map, indent=JSON_INDENT))


class ObjectTagHandler(TagHandler):
    
    def __init__(self, *args, **kwargs):
        super(ObjectTagHandler, self).__init__(*args, **kwargs)

        self.actions_found = 0
        self.has_folder = False

        self.attributes = collections.defaultdict(list)
        self.current_attribute = None

    def create_dir(self):
        if not self.has_folder:
            Parser().append_to_current_path(self.attrs["Name"])
            Parser().create_folder_from_current_path()
            DEBUG("Folder created - {}".format(Parser().current_path()))
            self.has_folder = True

    def child_start(self, tagname, attrs):
        if tagname == "Attribute":
            self.current_attribute = attrs["Name"]

        elif tagname == "Object":
            if not self.has_folder:
                self.create_dir()

            ObjectTagHandler(tagname, attrs).register()

        elif tagname == "Actions":
            ActionsTagHandler(tagname, attrs).register()

    def child_data(self, data):
        if self.current_attribute:
            self.attributes[self.current_attribute].append(encode(data))

    def child_end(self, tagname, depth=0):
        if tagname == "Attribute":
            self.current_attribute = None

        elif tagname == "Object":
            self.save()
            self.unregister()
       
    def save(self):
        name = INFO_JSON if self.has_folder or self.actions_found else "{}.json".format(self.attrs["Name"])

        data = {"attrs": self.attrs, "attributes": {k: clear_data("".join(v)) for k,v in self.attributes.items()}}
        Parser().write_file(name, json.dumps(data, indent=JSON_INDENT))

        if self.has_folder or self.actions_found :
            Parser().pop_from_current_path()


class E2vdomTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(E2vdomTagHandler, self).__init__(*args, **kwargs)
        self.current_mode = ""
        self.current_node = None
        self.accept_data = False

    def child_start(self, tagname, attrs):
        if tagname in ("Events", "Actions"):
            self.current_mode = tagname

        if tagname in ("Event", "Action") and self.current_mode == "Events":
            if tagname == "Event":
                self.current_node = attrs
                self.current_node["actions"] = []

            elif tagname == "Action":
                self.current_node["actions"].append(attrs["ID"])

        elif tagname in ("Action", "Parameter") and self.current_mode == "Actions":
            if tagname == "Action":
                self.current_node = attrs
                self.current_node["params"] = []

            elif tagname == "Parameter":
                self.current_node["params"].append([attrs["ScriptName"], []])
                self.accept_data = True

    def child_data(self, data):
        if self.accept_data:
            self.current_node["params"][-1][1].append(encode(data))

    def child_end(self, tagname):
        if tagname == "E2vdom":
            self.save()
            self.unregister()

        elif tagname == "Event" and self.current_mode == "Events":
            page = Parser().pages[self.current_node["ContainerID"]]
            page["events"].append(self.current_node)
            for action in self.current_node["actions"]:
                if not page["actions"].get(action, ""):
                    page["actions"][action] = ""

            self.current_node = ""

        elif tagname == "Events" and self.current_mode == "Events":
            self.current_mode = ""

        elif tagname == "Action" and self.current_mode == "Actions":
            for page in Parser().pages.values():
                if self.current_node["ID"] in page["actions"]:
                    page["actions"][self.current_node["ID"]] = self.current_node
                    break
   
            self.current_node = ""

        elif tagname == "Actions" and self.current_mode == "Actions":
            self.current_mode = ""

        elif tagname == "Parameter" and self.current_mode == "Actions":
            self.accept_data = False
            self.current_node["params"][-1][1] = "".join(self.current_node["params"][-1][1])


    def save(self):
        Parser().append_to_current_path("Pages")
        for page in Parser().pages.values():
            Parser().append_to_current_path(page["name"])
            Parser().write_file(
                E2VDOM_JSON, 
                json.dumps(
                    {
                        "events": page["events"], 
                        "actions": [v for v in page["actions"].values() if v]
                    }, 
                    indent=JSON_INDENT)
            )

            Parser().pop_from_current_path()

        Parser().pop_from_current_path()


class SecurityTagHandler(TagHandler):

    FOLDER = "Security"

    def __init__(self, *args, **kwargs):
        super(SecurityTagHandler, self).__init__(*args, **kwargs)
        self.groups = []
        self.users  = []
        self.current_mode = ""
        self.current_node = None
        self.accept_data = False
        self.ldapf = None

        self.create_base_dir()

    def create_base_dir(self):
        Parser().append_to_current_path(self.FOLDER)
        Parser().create_folder_from_current_path()

    def child_start(self, tagname, attrs):
        if tagname in ("Groups", "Users", "LDAP"):
            self.current_mode = tagname

        if self.current_mode == "Users":
            if tagname == "User":
                self.current_node = []

            elif tagname in ("Login", "Password", "FirstName", "LastName", "Email", "SecurityLevel", "MemberOf"):
                self.current_node.append([tagname, []])
                self.accept_data = True

            elif tagname == "Rights":
                self.current_node.append([tagname, []])

            elif tagname == "Right":
                self.current_node[-1][1].append(attrs)

        elif self.current_mode == "LDAP":
            self.ldapf = cStringIO.StringIO()
            self.accept_data = True

    def child_data(self, data):
        if self.accept_data:
            if self.current_mode == "Users":
                self.current_node[-1][1].append(encode(data))

            elif self.current_mode == "LDAP":
                self.ldapf.write(data)


    def child_end(self, tagname):
        if tagname == "Security":
            self.save()
            self.unregister()

        if self.current_mode == "Users":
            if tagname == "Users":
                self.current_mode = ""
                self.current_node = None

            elif tagname == "User":
                self.users.append(dict(self.current_node))

                # uncomment following string if order is important 
                # self.users.append(self.current_node) 

            elif tagname in ("Login", "Password", "FirstName", "LastName", "Email", "SecurityLevel", "MemberOf"):
                self.accept_data = False
                self.current_node[-1][1] = "".join(self.current_node[-1][1])

    def save(self):
        if self.users:
            Parser().write_file(
                USERS_JSON, 
                json.dumps(self.users, indent=JSON_INDENT)
            )

        if self.groups:
            Parser().write_file(
                GROUPS_JSON, 
                json.dumps(self.groups, indent=JSON_INDENT)
            )

        if self.ldapf:
            Parser().write_file(
                LDAP_LDIF,
                base64.b64decode(self.ldapf.getvalue())
            )


class StructureTagHandler(TagHandler):

    def __init__(self, *args, **kwargs):
        super(StructureTagHandler, self).__init__(*args, **kwargs)
        self.structure = []

    def child_start(self, tagname, attrs):
        if tagname == "Object":
            self.structure.append(attrs)

    def child_end(self, tagname):
        if tagname == "Structure":
            self.save()
            self.unregister()

    def child_data(self, data):
        pass

    def save(self):
        Parser().write_file(STRUCT_JSON, json.dumps(self.structure, indent=JSON_INDENT))


class ApplicationTagHandler(TagHandler):

    def create_dir(self):
        pass

    def child_start(self, tagname, attrs):
        TAG_HANDLERS_MAP = {
            "Information": InformationTagHandler,
            "Libraries": LibrariesTagHandler,
            "Resources": ResourcesTagHandler,
            "Databases": DatabasesTagHandler,
            "Objects": PagesTagHandler,
            "Actions": ActionsTagHandler,
            "E2vdom": E2vdomTagHandler,
            "Structure": StructureTagHandler,
            "Security": SecurityTagHandler,
        }

        handler_cls = TAG_HANDLERS_MAP.get(tagname, None)
        if handler_cls:
            handler_cls(tagname, attrs).register()
        

    def child_end(self, tagname, depth=0):
        if tagname == "Application":
            self.unregister()






class Parser(object):

    __instance = None
    
    def __new__(cls, *a, **kwa):
        if cls.__instance is None:
            cls.__instance = object.__new__(cls)
        return cls.__instance

    def initialize(self, src="", dst="", debug=False):
        self.debug = debug
        self.src = src
        self.dst = dst
        
        self.statisitcs = {
            "unknown": 0,
            "files": 0
        }

        self._handlers_stack = []
        self._current_path = []
        self.pages = {}

        return self

    def create_folder_from_current_path(self):
        os.makedirs(self.current_path())

    def current_path(self):
        return build_path(*self._current_path)

    def append_to_current_path(self, path):
        self._current_path.append(path)

    def pop_from_current_path(self):
        return self._current_path.pop()

    def write_file(self, name, data):
        path = build_path(self.current_path(), name)
        print path

        with open(path, "w") as f:
            f.write(data)

    @property
    def current_xml_path(self):
        return " > ".join(map(str, self.tag_handlers))

    @property
    def current_handler(self):
        return self.tag_handlers[-1]

    @property
    def tag_handlers(self):
        return self._handlers_stack

    def add_tag_handler_to_stack(self, handler):
        if handler not in self.tag_handlers:
            self.tag_handlers.append(handler)

        else:
            raise Exception("Handler register: handler already in stack")
    
    def remove_tag_handler_from_stack(self, handler):
        if self.tag_handlers[-1] != handler:
            raise Exception("Handler unregister: invalid handler")

        self.tag_handlers.pop()

    def start_element(self, tagname, attrs):
        """New element found
        """
        self.current_handler.child_start(tagname, attrs)

    def end_element(self, tagname):
        """Element closed
        """
        self.current_handler.child_end(tagname)

    def char_data(self, data):
        """Element data
        """
        self.current_handler.child_data(data)

    def start(self):
        """Setup logging and start main process
        """
        setup_logging(debug=self.debug)
        self.dst = create_dir(self.dst or "Application")
        self.append_to_current_path(self.dst)

        INFO("Destination folder created - {}".format(self.dst))

        RootHandler().register()

        p = xml.parsers.expat.ParserCreate()
        p.StartElementHandler = self.start_element
        p.EndElementHandler = self.end_element 
        p.CharacterDataHandler = self.char_data
        p.ParseFile(open(self.src))

        INFO("Destination folder - {}".format(self.dst))
        self.done()

    def done(self):
        """Finish parsing process and print statistics
        """
        pass

def create():
    return Parser().initialize()