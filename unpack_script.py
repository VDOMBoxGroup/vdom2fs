from __future__ import print_function
import shutil
import json, os, argparse, re

def index_files(config, index, skip_db):
    for category, settings in config.items():
        if category == "Aliases":
            continue
        if skip_db and category == "Databases":
            continue
        if category == "Actions":
            category = "Actions-Application"
        
        if isinstance(settings, dict):
            for key, value in settings.items():
                process_setting(value, index, category)
        elif isinstance(settings, list):
            for setting in settings:
                process_setting(setting, index, category)
        elif isinstance(settings, (str, unicode)):
            process_simple_path(settings, index, category)

def process_setting(value, index, category):
    if isinstance(value, dict) and "path" in value:
        normalized_path = normalize_path(value['path'], config)
        include_patterns = compile_regex_patterns(value.get('include', []))
        exclude_patterns = compile_regex_patterns(value.get('exclude', []))
        process_directory(normalized_path, index, category, include_patterns, exclude_patterns)
    elif isinstance(value, (str, unicode)):
        normalized_path = normalize_path(value, config)
        process_directory(normalized_path, index, category)

def process_simple_path(path, index, category):
    normalized_path = normalize_path(path, config)
    process_directory(normalized_path, index, category)

def process_directory(path, index, category, include_patterns=[], exclude_patterns=[]):
    
    if os.path.isfile(path):
        process_file(path, index, category, path)

    for root, dirs, files in os.walk(path):
        for file in files:
            if file.startswith('.'):
                continue
            if exclude_patterns and file_matches_patterns(file, exclude_patterns):
                continue
            if include_patterns and not file_matches_patterns(file, include_patterns):
                continue

            full_file_path = os.path.join(root, file)
            process_file(path, index, category, full_file_path)

def process_file(path, index, category, full_file_path):
    packed_file = os.path.relpath(full_file_path, os.path.abspath(os.path.join(path, os.pardir)))
    parts = packed_file.split(os.sep)
    if len(parts) > 1:
        packed_file = os.path.join(*parts[1:])

    if full_file_path.startswith('.'):
        full_file_path = os.path.join(parent_dir, full_file_path[2:])
    if category == "ApplicationInfo":
        index[packed_file] = os.path.dirname(full_file_path)
    index[os.path.join(category, packed_file)] = os.path.dirname(full_file_path)

def normalize_path(path, config):
    """Replace alias with real path
    """

    for alias, link in config["Aliases"].items():
        if path.startswith(alias):
            return path.replace(alias, link, 1)

    return path

def compile_regex_patterns(patterns):
    if not isinstance(patterns, list):
        patterns = [patterns]
    return [re.compile(pattern) for pattern in patterns]

def file_matches_patterns(file, patterns):
    return any(pattern.search(file) for pattern in patterns)

def unpack_app(index, unpack_dir, temp_dir):
    # Creating repos
    for alias, rel_path in config["Aliases"].items():
        dir_path = os.path.join(temp_dir, rel_path)

        if rel_path == ".":
            dir_path = os.path.join(temp_dir, parent_dir)
        else:
            dir_path = os.path.join(temp_dir, rel_path)
        
        key = parent_dir if rel_path == "." else rel_path

         
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print("Directory created: {}".format(dir_path))
        else:
            print("Directory already exists: {}".format(dir_path))

    # Adding directory for new files
    new_files_dir = os.path.join(temp_dir, "new_files")
    if not os.path.exists(new_files_dir):
        os.makedirs(new_files_dir)
        print("Directory created: {}".format(new_files_dir))
    else:
        print("Directory already exists: {}".format(new_files_dir))

    unpack_path = os.path.abspath(unpack_dir)
    for root, dirs, files in os.walk(unpack_path):
        if skip_db:
            dirs[:] = [d for d in dirs if d != 'Databases']
        
        for file in files:
            if file.startswith('.'):
                continue
                   
            full_file_path = os.path.join(root, file)
            relative_file_path = os.path.relpath(full_file_path, unpack_path)
            file_path = index.get(relative_file_path)

            if file_path:
                dest_path = os.path.join(temp_dir, file_path)
                if not dest_path.endswith(os.sep):
                    dest_path += os.sep
                try:
                    os.makedirs(os.path.dirname(dest_path))
                except OSError as e:
                    if e.errno != os.errno.EEXIST:  # ignore error if it's folder exists error
                        raise  # otherwise throw exception
                shutil.copy(full_file_path, dest_path)
            else:
                parts = relative_file_path.split(os.sep)
                dir_path = new_files_dir
                for part in parts[:-1]:  # excluding filename from iteration
                    dir_path = os.path.join(dir_path, part)
                    if not dir_path.endswith(os.sep):
                        dir_path += os.sep
                    if not os.path.exists(dir_path):
                        try:
                            os.makedirs(dir_path)
                        except OSError as e:
                            if e.errno != os.errno.EEXIST:
                                raise

                dest_path = os.path.join(new_files_dir, relative_file_path)
                shutil.copy(full_file_path, dest_path)

parser = argparse.ArgumentParser(description="This script unpacks VDOM apps back to repos they made of using vdom2fx.conf file")

parser.add_argument("--config_path", type=str, default="vdom2fs.conf", help="Path to the configuration file")
parser.add_argument("--indexes_path", type=str, default=".tmp/index.json", help="Path to the indexes file")
parser.add_argument("--temp_dir", type=str, default=".tmp/changes", help="Path to the temporary directory")
parser.add_argument("--unpack_dir", type=str, default=".tmp/unpack", help="Path to the app directory")
parser.add_argument("--parent_dir", type=str, default=os.path.basename(os.getcwd()), help="Path to the parent directory")
parser.add_argument("--skip_db", type=bool, default=True, help="Flag to skip database processing")
parser.add_argument("--no_index", type=bool, default=False, help="Flag to skip indexing repos")

args = parser.parse_args()

config_path = args.config_path
indexes_path = args.indexes_path 
temp_dir = args.temp_dir
unpack_dir = args.unpack_dir
parent_dir = args.parent_dir
skip_db = args.skip_db
no_index = args.no_index

with open(config_path, 'r') as file:
    config = json.load(file)

# Making sure that directory is exists
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# Saving indexes
index = {}
if no_index:
    with open(indexes_path, 'r') as index_file:
        index = json.load(index_file)
else:
    index_files(config, index, skip_db)
    with open(indexes_path, 'w') as index_file:
        json.dump(index, index_file, indent=4)        

unpack_app(index, unpack_dir, temp_dir)


    

