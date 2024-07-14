#!/usr/bin/env python3

import datetime
import os
import shutil
import smtplib, ssl
import sys

port = 25  # Local smtp server
smtp_server = "localhost"
sender_email = "mike@webtide.co.za"
receiver_email = "mike@metcalfe.co.za"
faile_message = """\
Subject: Hydrochem Sync Log Missing

The Hydrochem Sync log file cannot be found for today
"""
success_message = """\
Subject: Hydrochem Sync Log Found

The Hydrochem Sync log file found for today
"""

context = ssl.create_default_context()
SYNC_BASE_FOLDER = "/home/senaite/sync"
SYNC_LOGS_FOLDER = "{}/logs".format(SYNC_BASE_FOLDER)


def find_todays_log_file():
    print("Start")
    ls = os.listdir(SYNC_LOGS_FOLDER)
    if len(ls) == 0:
        print(f"No log files found in {SYNC_LOGS_FOLDER}")
        return
    # import pdb; pdb.set_trace()
    runtime = datetime.date.today().strftime("%Y%m%d")
    for file_name in ls:
        if runtime in file_name:
            return file_name
    return

def check_for_logfile():
    file_name = find_todays_log_file()
    if file_name is None:
        # Send email
        print("Did not find today's log file")
        with smtplib.SMTP(smtp_server, port) as server:
            server.sendmail(sender_email, receiver_email, fail_message)
    else:
        # All good
        print(f"Found today's log file {file_name}")
        with smtplib.SMTP(smtp_server, port) as server:
            server.sendmail(sender_email, receiver_email, success_message)


if __name__ == "__main__":
    check_for_logfile()
