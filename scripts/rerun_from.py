#!/usr/bin/env python3

import datetime
import requests
import os
import sys
import time

SYNC_BASE_FOLDER = "/home/senaite/sync"
SYNC_CURRENT_FOLDER = "{}/current".format(SYNC_BASE_FOLDER)

def invoke_sync(user, password):
    url = "https://lims.hydrochem.com.au/@@sync_locations_view?get_emails=false&commit=true"
    print(f"get url {url}")

    response = requests.get(url, auth=(user, password)

    # import pdb; pdb.set_trace()
    if response.status_code != 200:
        print(f"invoke_sync failed: {response.status_code}")
        return False
    if response.url == "https://lims.hydrochem.com.au/login":
        print(f"invoke_sync failed: {response.url}")
        return False

    return True


def return_files(from_date, to_date, action, user, password):
    print(f'Start with action {action} dates {from_date} {to_date}')
    # for folder in [SYNC_BACKUP_FOLDER, SYNC_ARCHIVE_FOLDER, SYNC_ERROR_FOLDER]:
    try:
        from_date = datetime.datetime.strptime(from_date, "%Y%m%d").date()
        to_date = datetime.datetime.strptime(to_date, "%Y%m%d").date()
    except Exception as e:
        raise(e)

    adate = from_date
    while True:
        files = os.listdir(SYNC_CURRENT_FOLDER)
        if len(files) > 0:
            time.sleep(3)
            continue
        date_str = adate.strftime("%Y%m%d")
        cmd = f"/home/senaite/sync/bin/rerun_files.py {date_str} copy"
        print(cmd)
        if action == 'prod':
            os.system(cmd)
        time.sleep(1)
        if action == 'prod':
            if not invoke_sync(user, password):
                break

        adate = adate + datetime.timedelta(days=1)
        if adate > to_date:
            break
    print("Done")

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print('from-date, to-date, action, user and password arguments are all required')
    else:
        from_date = sys.argv[1]
        to_date = sys.argv[2]
        action = sys.argv[3]
        user = sys.argv[4]
        password = sys.argv[5]
        if action not in ['prod', 'test']:
            print(f'action {action} not in [prod, test]')
        else:
            print(f'Call with action {action} dates {from_date} {to_date}')
            return_files(from_date, to_date, action, user, password)


