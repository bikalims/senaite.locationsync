#!/usr/bin/env python3
"""
get_ftp_files.py

Connect to the speficied FTP server and copy files from a remote directory
to a local directory, and send out an email after.

To see all the arguments
python ./get_ftp_files.py --help


"""
import argparse
import datetime
from ftplib import FTP
import logging
import re
import smtplib

now = datetime.datetime.now().strftime("%Y%m%d.%H%M")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("get_ftp_files")
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh = logging.FileHandler(f"/home/senaite/sync/logs/get_ftp_files-{now}.log")
fh.setFormatter(formatter)
logger.addHandler(fh)

port = 25  # Local smtp server
smtp_server = "localhost"
sender_email = "lunga@bikalims.com"
receiver_email = "lunga001@gmail.com"
fail_message = """\
Subject: Hydrochem Sync FTP Files Missing

No Hydrochem Sync files found on FTP server
"""
success_message = """\
Subject: Hydrochem Sync FTP Files Found

{} Hydrochem Sync files found on FTP server
"""


def connect_ftp(server, port, username, password):
    """Connect to the FTP server."""
    try:
        ftp = FTP()
        msg = ftp.connect(server, port)
        logger.info(f"FTP server replied: {msg}")
        logger.info(f"Connected to server {server} on port {port}")
    except Exception as e:
        logger.error(f"Failed to connect to server {server} on port {port}: error {e}")
        raise
    try:
        msg = ftp.login(username, password)
        logger.info(f"FTP server replied: {msg}")
        logger.info(f"Logged into server {server} with user {username}")
    except Exception as e:
        logger.error(
            f"Failed to login to server {server} with user {username}: username or password in incorrect [error {e}]"
        )
        raise
    return ftp


def list_files(ftp, directory):
    """List files in the specified directory."""
    msg = ftp.cwd(directory)
    logger.info(f"FTP server replied: {msg}")
    files = ftp.nlst()
    logger.info(f"Files in remote directory: {files}")
    logger.info(f"Found {len(files)} files in {directory}")
    return files


def download_file(args, ftp, filename, local_filename):
    """Download a file from the FTP server."""
    logger.info(f"Download file {filename} to {local_filename}")
    with open(local_filename, "wb") as local_file:
        msg = ftp.retrbinary(f"RETR {filename}", local_file.write)
        logger.info(f"FTP server replied: {msg}")

def delete_file(args, ftp, filename):
    """Delete a file from the FTP server."""
    logger.info(f"Delete file {filename}")
    msg = ftp.delete(filename)
    logger.info(f"FTP server replied: {msg}")


def main():
    # Argument parsing
    parser = argparse.ArgumentParser(
        description="Download files with a specific date from an FTP server."
    )
    parser.add_argument(
        "-s", "--server", type=str, help="FTP server address", required=True
    )
    parser.add_argument(
        "-sp", "--server_port", type=int, default=21, help="FTP server address"
    )
    parser.add_argument(
        "-u", "--username", type=str, help="FTP username", required=True
    )
    parser.add_argument(
        "-p", "--password", type=str, help="FTP password", required=True
    )
    parser.add_argument(
        "-r",
        "--remote_directory",
        type=str,
        help="Remote directory to list files from",
        required=True,
    )
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        help="Date to filter files by - see date_pattern for format",
    )
    parser.add_argument(
        "-dp",
        "--date_pattern",
        type=str,
        help="date pattern to filter files using python strftime format",
        # default="%Y%m%d",
        default="",
    )
    parser.add_argument(
        "-dr",
        "--date_range",
        action="store_true",
        help="Get all file from given date to today",
    )
    parser.add_argument(
        "-l",
        "--local_directory",
        type=str,
        help="Local directory to save downloaded files",
        required=True,
    )
    parser.add_argument(
        "-b",
        "--local_backup",
        type=str,
        help="Local directory to backup timestamped files",
        required=False,
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Don't copy files",
    )
    parser.add_argument(
        "-e",
        "--send_email",
        action="store_true",
        help="Send out email",
    )
    args = parser.parse_args()
    if args.date is None:
        args.date = datetime.datetime.today().date().strftime(args.date_pattern)

    logger.info(
        f"Run get_ftp_files: server={args.server}:{args.server_port}, user={args.username}, remote_directory={args.remote_directory} and local_directory={args.local_directory}"
    )
    # Connect to the FTP server
    ftp = connect_ftp(args.server, args.server_port, args.username, args.password)

    try:
        # List files in the remote directory
        files = list_files(ftp, args.remote_directory)

        try:
            from_date = datetime.datetime.strptime(args.date, args.date_pattern).date()
        except Exception as e:
            logger.error(
                f"Failed to parse date {args.date} with pattern {args.date_pattern}"
            )
            raise (e)

        to_date = datetime.datetime.today().date()

        adate = from_date
        # Walk through the dates
        # Download files that match the date pattern
        cnt = 0
        while True:
            date_str = adate.strftime(args.date_pattern)
            logger.debug(f"Look for file on date {date_str}")
            for filename in files:
                # Create a regex pattern for the date
                re_date_pattern = re.compile(re.escape(date_str))
                if re_date_pattern.search(filename):
                    # Download to local
                    local_filename = f"{args.local_directory}/{filename}"
                    if not args.dry_run:
                        download_file(args, ftp, filename, local_filename)

                    # Download to local backup
                    if args.local_backup:
                        local_filename = filename.split('.csv')[0]
                        local_filename = f"{args.local_backup}/{local_filename}.{now}.csv"
                        if not args.dry_run:
                            download_file(args, ftp, filename, local_filename)

                    if not args.dry_run:
                        delete_file(args, ftp, filename)
                    cnt += 1
                else:
                    logger.info(f"File {filename} does not match the date pattern {date_str}")

            if not args.date_range:
                break

            adate = adate + datetime.timedelta(days=1)
            if adate > to_date:
                break

        logger.info(f"Downloaded {cnt} files")

        if args.send_email:
            logger.info("SendEmail: enabled")
            if cnt == 0:
                # Send email
                logger.info("SendEmail: Did not find today's sync file")
                with smtplib.SMTP(smtp_server, port) as server:
                    server.sendmail(sender_email, receiver_email, fail_message)
            else:
                # All good
                logger.info(f"SendEmail: Found today's sync file {args.date}")
                with smtplib.SMTP(smtp_server, port) as server:
                    server.sendmail(
                        sender_email, receiver_email, success_message.format(cnt)
                    )
        else:
            logger.info("SendEmail: disabled")

    finally:
        # Always close the connection
        msg = ftp.quit()
        logger.info(f"FTP server replied: {msg}")
    logger.info("Script complete")


if __name__ == "__main__":
    main()
