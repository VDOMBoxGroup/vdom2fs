#!/usr/bin/env python
# encoding: utf-8


DATABASES_FOLDER = "Databases"
LIBRARIES_FOLDER = "Libraries"
PAGES_FOLDER = "Pages"
RESOURCES_FOLDER = "Resources"
SECURITY_FOLDER = "Security"
APP_ACTIONS_FOLDER = "Actions-Application"


INFO_FILE = "__info__.json"
MAP_FILE = "__map__.json"

SVN_FOLDER = ".svn"
GIT_FOLDER = ".git"


BASE_FOLDERS = (
    DATABASES_FOLDER,
    LIBRARIES_FOLDER,
    PAGES_FOLDER,
    RESOURCES_FOLDER,
    SECURITY_FOLDER
)


DO_NOT_DELETE = (
    SVN_FOLDER,
    GIT_FOLDER
)
