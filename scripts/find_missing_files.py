#!/usr/bin/env python3

import datetime
import requests
import os
import sys
import time

SYNC_BASE_FOLDER = "/home/senaite/sync"
SYNC_ALL_FOLDER = "{}/all".format(SYNC_BASE_FOLDER)
FILE_NAMES = ['Account lims', 'attention contact lims', 'system lims', 'location lims']

def find_files(from_date):
    try:
        from_date = datetime.datetime.strptime(from_date, "%Y%m%d").date()
        to_date = datetime.datetime.today().date()
    except Exception as e:
        raise(e)

    print(f'Find from {from_date} to {to_date}')
    files = os.listdir(SYNC_ALL_FOLDER)
    if len(files) == 0:
        print(f"No files found in {SYNC_BASE_FOLDER}")
        return
    adate = from_date
    # Walk through the dates
    cnt = 0
    while True:
        date_str = adate.strftime("%Y%m%d")
        for prefix in FILE_NAMES:
            name = f"{prefix}.{date_str}"
            results = [f for f in files if f.startswith(name)]
            if len(results) == 0:
                print(f"File not found: {prefix}.csv on {date_str}")
                cnt += 1
            elif len(results) > 1:
                print(f"Multiple files found for: {name}")

        adate = adate + datetime.timedelta(days=1)
        if adate > to_date:
            break
    print(f"Found {cnt} missing file from {from_date} to {to_date}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('from date isl required')
    else:
        from_date = sys.argv[1]
        find_files(from_date)


