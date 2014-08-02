#!/usr/bin/env python
# encoding: utf-8


APP_ACTIONS_FOLDER = "Actions-Application"
DATABASES_FOLDER = "Databases"
LIBRARIES_FOLDER = "Libraries"
PAGES_FOLDER = "Pages"
RESOURCES_FOLDER = "Resources"
SECURITY_FOLDER = "Security"
GIT_FOLDER = ".git"
SVN_FOLDER = ".svn"
OS_X_FOLDER = ".DS_Store"

E2VDOM_FILE = "__e2vdom__.json"
INFO_FILE = "__info__.json"
LIBRARIES_FILE = "__libraries__.json"
LDAP_LDIF = "__ldap__.ldif"
MAP_FILE = "__map__.json"
RESOURCES_FILE = "__resources__.json"
STRUCT_FILE = "__struct__.json"
USERS_GROUPS_FILE = "__users_groups__.json"

BASE_FOLDERS = (
    DATABASES_FOLDER,
    LIBRARIES_FOLDER,
    PAGES_FOLDER,
    RESOURCES_FOLDER,
    SECURITY_FOLDER,
    APP_ACTIONS_FOLDER
)

DO_NOT_DELETE = (
    SVN_FOLDER,
    GIT_FOLDER
)

RESERVED_NAMES = (
    E2VDOM_FILE,
    INFO_FILE,
    LDAP_LDIF,
    MAP_FILE,
    RESOURCES_FILE,
    STRUCT_FILE,
    USERS_GROUPS_FILE,
    SVN_FOLDER,
    GIT_FOLDER,
    LIBRARIES_FILE,
    OS_X_FOLDER
)
