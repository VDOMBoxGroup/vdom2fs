# VDOM  Python 2 to 3 Web App Porting Tool

## Description

This script is designed to facilitate the process of porting VDOM web applications written in Python 2 to Python 3. It automatically modifies the source code of XML web applications to make them compatible with Python 3.

## Requirements

* Python 3.x
* argparse module installed

## Key Features
* Automatic Conversion of print Statements: The script searches for and converts outdated Python 2 print statements to the Python 3 syntax.
* Module Import Fixing: The script updates module imports, a common compatibility issue when transferring code from Python 2 to Python 3. Imports from a specified directory are modified for correct functioning in the new environment.
* Flexible Command Line Configuration: The script accepts paths to the source file and module directory through command-line arguments, making it convenient for integration into various workflows.

## Usage

To use the script, specify the path to the source XML file, the path to the directory with Python modules, and optionally, the path to the output file.

```
python xml2to3.py <file_path> <modules_folder> [<output_file>]
```

## Examples

To convert a file, saving the result in a new file with .tmp appended:

```
python xml2to3.py my_script.xml my_modules
```

To convert a file, specifying the path to the output file:

```
python xml2to3.py my_script.xml my_modules modified_script.xml
```
