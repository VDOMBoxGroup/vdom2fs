import re, os, argparse

parser = argparse.ArgumentParser(description="Script to port VDOM xml apps from 2 python to 3")

parser.add_argument("file_path", help="Path to the source xml app file")
parser.add_argument("modules_folder", help="Path to the directory containing modules")
parser.add_argument("-o", "--output", help="Path to the output file (default: <file_path>.tmp)", default=None)

args = parser.parse_args()

file_path = args.file_path
modules_folder = args.modules_folder
output_file = args.output if args.output else file_path + '.tmp'

modules = {file.split('.')[0] for file in os.listdir(modules_folder) if file.endswith('.py')}

pattern_import_from = r"(.*?from\s+)(\w+)(\s+import\s+[\w*,\s]+)"
pattern_print = r'print\s*("([^"]*)"|\'([^\']*)\')'
pattern_import = r"(^.*?)(import\s)([\w_]+)"
pattern_except = r"except\s+([A-Za-z0-9_]+)\s*,\s*([a-z][A-Za-z0-9_]*)\s*:"
except_replacement = r"except \1 as \2:"



def replace_import_from(match):
    prefix, module, postfix = match.groups()
    if module in modules:
        return f"{prefix} .{module} {postfix}"
    else:
        return match.group(0)

def replace_import(match):
    prefix, imp, module = match.groups()
    if module in modules:
        return f"{prefix}from . import {module}"
    else:
        return match.group(0)

def replace_print(match):
    if match.group(2):
        return 'print("{}")'.format(match.group(2))
    else:
        return "print('{}')".format(match.group(3))

def process_line(line):
    if re.match(pattern_import_from, line):
        line = re.sub(pattern_import_from, replace_import_from, line)
    else:
        line = re.sub(pattern_import, replace_import, line)
    
    line = re.sub(pattern_print, replace_print, line)
    line = re.sub(pattern_except, except_replacement, line)
    return line

with open(file_path, 'r', encoding='utf-8') as file, open(file_path + '.tmp', 'w', encoding='utf-8') as outfile:
     for line in file:
        line = process_line(line)
        outfile.write(line)
        
print(f"File processed. Output saved to '{output_file}'.")