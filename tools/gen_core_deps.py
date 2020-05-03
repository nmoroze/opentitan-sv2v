#!/usr/bin/env python3

'''
Read a FuseSOC *.core file, gather all dependencies, and output them in a useful
format.

Likely doesn't work generically, only supports subset of features needed to
gather dependencies for LowRISC OpenTitan.

FuseSOC documentation (see section "CAPI2" for *.core file specification):
https://readthedocs.org/projects/fusesoc/downloads/pdf/stable/
'''

import os
from pathlib import Path
import yaml

all_files = []
checked_dependencies = set()

# Directory to recursively search for dependencies
# Current default assumes running this script from shiva-ibex top level
INC_DIR = "soc/opentitan/hw"
# Text outputted before outputting dependencies
OUTPUT_PROLOGUE = """# File autogenerated by running:
# ./tools/gen_core_deps.py soc/opentitan/hw/top_earlgrey/top_earlgrey.core >
#   ot_srcs.mk

OT_SRCS := """

# Seperator between filenames in final printed output
OUTPUT_SEPERATOR = "\nOT_SRCS += "
# Toggle verbose output
VERBOSE = False

# For now ignore version suffix, since it doesn't seem to matter in our case
# e.g. lowrisc:ip:uart:0.1 -> lowrisc:ip:uart
def strip_version(name):
    if len(name.split(':')) > 3:
        return ":".join(name.split(':')[0:3])

    return name

# Given a path, recursively search for *.core files and return a dictionary with
# core names as keys and full paths as values.
def find_core_files(search_path):
    core_files = {}
    for file_path in search_path.rglob('*.core'):
        with open(file_path, 'r') as core_file:
            core_data = yaml.safe_load(core_file.read())
            name = core_data["name"]
            core_files[strip_version(name)] = file_path

    return core_files

# Given a top level *.core file path, recursively gather all dependency RTL
# files and add unique ones to all_files global list. Also takes in dictionary
# mapping dependency names to paths (can be generated using find_core_files).
def gather_files(top_level_filename, core_files):
    paths = []
    dependencies = []

    if VERBOSE: print("Gathering files for {}".format(top_level_filename))

    with open(top_level_filename, 'r') as core_file:
        core_data = yaml.safe_load(core_file.read())
        try:
            filesets = core_data['filesets']
            if 'files_rtl_generic' in filesets:
                paths += filesets['files_rtl_generic'].get('files', [])
                dependencies += filesets['files_rtl_generic'].get('depend', [])
            if 'files_rtl' in filesets:
                paths += filesets['files_rtl'].get('files', [])
                dependencies += filesets['files_rtl'].get('depend', [])
        except KeyError as e:
            print("Key {} not found in file {}".format(e, top_level_filename))
            raise e

    top_level_path = Path(top_level_filename).parent

    # Give each file an absolute path, and add it if it hasn't been counted
    # already
    for path in paths:
        abs_path = Path.joinpath(Path(top_level_path), Path(path))
        if abs_path not in all_files:
            all_files.append(abs_path)

    # Recursively gather files for each dependency we haven't checked already
    for dependency in dependencies:
        stripped_name = strip_version(dependency)
        if stripped_name not in checked_dependencies:
            gather_files(core_files[stripped_name], core_files)
            checked_dependencies.add(stripped_name)

def main():
    if len(os.sys.argv) != 2:
        print("Error: expected 1 argument")
        return

    core_files = find_core_files(Path(INC_DIR).resolve())
    if VERBOSE:
        print("Core files found:\n{}"
              .format("\n"
              .join([f'{k} ({v})' for k, v in core_files.items()])))

    top_level_core_file = Path(os.sys.argv[1]).resolve(strict=True)

    gather_files(top_level_core_file, core_files)

    print(OUTPUT_PROLOGUE, end="")
    print(OUTPUT_SEPERATOR.join([
        str(path.relative_to(Path.cwd())) for path in all_files
    ]))

if __name__ == "__main__":
    main()
