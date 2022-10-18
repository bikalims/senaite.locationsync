import os

SYNC_BASE_FOLDER = "/home/mike/sync"
SYNC_CURRENT_FOLDER = "{}/current".format(SYNC_BASE_FOLDER)
SYNC_ARCHIVE_FOLDER = "{}/archive".format(SYNC_BASE_FOLDER)
SYNC_ERROR_FOLDER = "{}/errors".format(SYNC_BASE_FOLDER)


def _move_file(file_name, src_folder, dest_folder):
    from_file_path = "{}/{}".format(src_folder, file_name)
    to_file_path = "{}/{}".format(dest_folder, file_name)
    os.rename(from_file_path, to_file_path)


def return_files_to_current():
    print("Start")
    for folder in [SYNC_ARCHIVE_FOLDER, SYNC_ERROR_FOLDER]:
        ls = os.listdir(folder)
        if len(ls) == 0:
            continue
        for file_name in ls:
            print("{} from {}".format(file_name, folder))
            _move_file(file_name, folder, SYNC_CURRENT_FOLDER)
    print("Done")


if __name__ == "__main__":
    return_files_to_current()
