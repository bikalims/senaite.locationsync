#!/usr/bin/env python3

import os
import shutil
import sys

SYNC_BASE_FOLDER = "/home/senaite/sync"
SYNC_BACKUP_FOLDER = "{}/all".format(SYNC_BASE_FOLDER)
SYNC_CURRENT_FOLDER = "{}/current".format(SYNC_BASE_FOLDER)
SYNC_ARCHIVE_FOLDER = "{}/archive".format(SYNC_BASE_FOLDER)
SYNC_ERROR_FOLDER = "{}/errors".format(SYNC_BASE_FOLDER)


def move_file(file_name, src_folder, dest_folder, action='move'):
    from_file_path = "{}/{}".format(src_folder, file_name)
    parts = file_name.split(".")
    file_name = "{}.csv".format(".".join(parts[:-3]))
    to_file_path = "{}/{}".format(dest_folder, file_name)
    if action == 'move':
        os.rename(from_file_path, to_file_path)
    else:
        print(f"cp {from_file_path} {to_file_path}")
        shutil.copy(from_file_path, to_file_path)


def return_files_to_current(runtime, action):
    print("Start")
    # for folder in [SYNC_BACKUP_FOLDER, SYNC_ARCHIVE_FOLDER, SYNC_ERROR_FOLDER]:
    for folder in [SYNC_BACKUP_FOLDER, ]:
        ls = os.listdir(folder)
        if len(ls) == 0:
            continue
        for file_name in ls:
            if runtime in file_name:
                print("{} from {}".format(file_name, folder))
                if action != 'find':
                    move_file(file_name, folder, SYNC_CURRENT_FOLDER, action)
    print("Done")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('run time and action required')
    else:
        runtime = sys.argv[1]
        action = sys.argv[2]
        if action not in ['move', 'copy', 'find']:
            print(f'action {action} not in [move, copy, find]')
        else:
            print(f'action {action} date {runtime}')
            return_files_to_current(runtime, action)

