"""
#!/usr/bin/env python3
get_email.py - Designed to be run from cron, this script checks the pop3 mailbox
Based on django-helpdesk's get_email.py. inus@bikalabs.com 2022-10-17

Live params:
python get_email.py --user zzzz --server pop.zzzz.com --pop3 --password zzzz --valid NoReply@zzzz.com.zzzz --match '.* lims' --file_path '/home/zzzz/sync/current'
"""
from __future__ import print_function

import argparse
import email
from email.header import decode_header
from email.utils import parseaddr, collapse_rfc2231_value
import imaplib
import logging
import mimetypes
import os
import poplib
import re
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("getEmail")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh = logging.FileHandler("/home/senaite/sync/logs/emails.log")
fh.setFormatter(formatter)
logger.addHandler(fh)

months_conversion = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}

MAIL_FOLDER = "Processed"


def parse_uid(data):
    return str(data).replace("'", "").replace(")", "").split(" ")[-1]


def process_imap(args):
    server = imaplib.IMAP4_SSL(args.server)
    server.login(args.user, args.password)
    server.select(args.inbox[0])
    status, data = server.search(None, "NOT", "DELETED")
    if not args.quiet:
        logger.info(
            "Info: imap login to {} as {}, {} messages in folder {} ".format(
                args.server, args.user, len(data[0].split()), args.inbox[0]
            )
        )
    file_path = "."
    if args.file_path:
        file_path = args.file_path
        if type(file_path) == list and len(file_path) == 1:
            file_path = file_path[0]
    print(f"Sync file path = {file_path}")
    if data:
        msgnums = data[0].split()
        for num in msgnums:
            status, data = server.fetch(num, "(RFC822)")
            if file_from_message(
                message=data[0][1],
                file_path=file_path,
                quiet=args.quiet,
                rename=args.rename,
            ):
                if args.delete:
                    # Move is a copy and delete
                    resp, data = server.fetch(num, "(UID)")
                    msg_uid = parse_uid(data[0])
                    server.uid("COPY", msg_uid, MAIL_FOLDER)
                    server.uid("STORE", msg_uid, "+FLAGS", "\\Deleted")
                    # server.store(num, "+FLAGS", "\\Deleted")
                    if not args.quiet:
                        logger.info("Info: Message #{} deleted ".format(num))

    server.expunge()
    server.close()
    server.logout()

def process_pop3(args):
    server = poplib.POP3_SSL(args.server)
    server.getwelcome()
    response = server.user(args.user)
    response = server.pass_(args.password)
    response, messagesInfo, octets = server.list()

    if not args.quiet:
        logger.info(
            "Info: pop3 login to {} as {}, {} messages ".format(
                args.server, args.user, len(messagesInfo)
            )
        )
    file_path = "."
    if args.file_path:
        file_path = args.file_path
        if type(file_path) == list and len(file_path) == 1:
            file_path = file_path[0]
    print(f"Sync file path = {file_path}")
    for msg in messagesInfo:
        try:  # Sometimes messages are in bytes???
            msg = msg.decode("utf-8")
        except Exception:
            pass  # wasn't necessary
        try:
            msgNum = int(msg.split(" ")[0])
            # msgSize = int(msg.split(" ")[1])

            response, message_lines, octets = server.retr(msgNum)
            for i in range(len(message_lines)):  # in case message is binary
                try:
                    message_lines[i] = message_lines[i].decode("utf-8")
                except Exception:
                    pass

            if sys.version_info < (3,):
                full_message = "\n".join(message_lines)
            else:
                full_message = "\n".join(message_lines).encode()
            if file_from_message(
                message=full_message,
                file_path=file_path,
                quiet=args.quiet,
                rename=args.rename,
            ):
                if args.delete:
                    server.dele(msgNum)
                    logger.info("Deleted message # {}".format(msgNum))
                else:
                    logger.debug(
                        "Message #{} not deleted, -d not specified".format(msgNum)
                    )
            else:
                logger.info("File not saved, message #{} not deleted".format(msgNum))

        except Exception as e:
            logger.error(
                "Error: Exception process_email, message #{}, {}".format(msg, e)
            )
    server.quit()


def decodeUnknown(charset, string):
    if not charset:
        try:
            return string.decode("UTF_8", "ignore")
        except Exception:
            try:
                return string.decode("iso8859-1", "ignore")
            except Exception:
                return string
    try:
        return str(string, charset)
    except Exception:
        try:
            return bytes(string, "UTF_8")
        except Exception:
            return string.decode("UTF_8", "ignore")


def decode_mail_headers(string):
    decoded = decode_header(string)
    return decoded[0][0]


def file_from_message(message, file_path=".", quiet=False, rename=False):
    # 'message' must be an RFC822 formatted message.
    logger.debug("inside file_from_message")
    msg = message

    if sys.version_info < (3,):
        message = email.message_from_string(msg)
    else:
        message = email.message_from_string(msg.decode())

    subject = message.get("subject", "No subject.")
    subject = decode_mail_headers(decodeUnknown(message.get_charset(), subject))
    subject = str(subject)
    sender = message.get("from", "Unknown Sender")
    sender = decode_mail_headers(decodeUnknown(message.get_charset(), sender))

    logger.info(f"file_from_message: subject {subject}")
    try:  # in case it's binary. Seems like sometimes it is and sometimes it isn't :-/
        sender = sender.decode("utf-8")
    except Exception:
        pass

    sender_email = "".join(parseaddr(sender)[1])
    logger.info(f"file_from_message: sender {sender_email}")

    body_plain = ""
    accept_sender = False
    for s in Xargs.valid:
        logger.info(f"Process valid {s}")
        try:
            re.match(s, sender_email)
        except Exception:
            logger.error(
                'Invalid regular expression "{}" for sender {}, subject "{}".'.format(
                    s, sender_email, subject
                )
            )
            return False

        if re.match(s, sender_email):
            logger.debug('Sender match: "{}".'.format(sender))
            accept_sender = True
    if not accept_sender:
        logger.error('Ignoring mail from {}. Subject "{}".'.format(sender, subject))
        if Xargs.ignore:
            return True  # and delete
        else:
            return False
    logger.info("Email is valid")

    for s in Xargs.match:
        logger.info(f"Process match {s}")
        try:
            matchobj = re.match(s, subject)
        except Exception:
            logger.error(
                'Invalid regular expression "{}" for sender {}, subject "{}".'.format(
                    s, sender, subject
                )
            )
            return False

        if matchobj is None:
            logger.info('Subject NOT matched: "{}".'.format(subject))
            return False

        if not quiet:
            logger.info('Subject match: "{}".'.format(matchobj.string))

        counter = 0
        files = []

        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue

            name = part.get_param("name")
            if name:
                name = collapse_rfc2231_value(name)

            if part.get_content_maintype() == "text" and name is None:
                if part.get_content_subtype() == "plain":
                    body_plain = decodeUnknown(
                        part.get_content_charset(), part.get_payload(decode=True)
                    )
                else:
                    # TODO - what happens with html
                    part.get_payload(decode=True)
            else:
                if not name:
                    ext = mimetypes.guess_extension(part.get_content_type())
                    name = "part-%i%s" % (counter, ext)

            if (
                part.get_content_maintype() == "text"
                and part.get_content_subtype() == "csv"
            ):
                files.append(
                    {
                        "filename": name,
                        "content": part.get_payload(decode=True),
                        "type": part.get_content_type(),
                    },
                )

            counter += 1

        if body_plain:
            body = body_plain
        else:
            body = "No plain-text email body"
        logger.debug(f"Body test: {body}")
        for afile in files:
            if afile["content"]:  # and afile['filename']:
                if afile["filename"]:
                    if sys.version_info < (3,):
                        filename = afile["filename"].encode("ascii", "replace")
                    else:
                        filename = afile["filename"]

                    # filename = afile["filename"].replace(" ", "_")
                    # filename = re.sub("[^a-zA-Z0-9._-]+", "", filename)
                    if rename:  # Add date stamp to file names
                        # import pdb; pdb.set_trace()
                        parts = filename.split(".")
                        if parts and parts[-1] == "csv":
                            date = message.get("Date").split(" ")
                            time = date[3][:-3].replace(":", "")
                            date = f"{date[2]}{months_conversion[date[1]]}{int(date[0]):02d}.{time}"
                            parts.insert(-1, date)
                            filename = f"{'.'.join(parts)}"
                    filename = f"{file_path}/{filename}"
                    try:
                        f = open(filename, "w")

                        if sys.version_info < (3,):
                            f.write(afile["content"])
                        else:
                            f.write(afile["content"].decode())

                        f.close()
                        logger.info(f"Saved file {filename}")
                    except Exception as e:
                        logger.error(
                            "Error: Attachment not saved: {}, error {}".format(
                                filename, e
                            )
                        )
                        return False
                    if not quiet:
                        logger.info("Attachment saved as {}".format(filename))
        return True


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Retrieve email attachments.")
    parser.add_argument(
        "--quiet",
        "-q",
        default=False,
        action="store_true",
        help="Hide details about each queue/message as they are processed",
    )
    parser.add_argument(
        "--pop3",
        "-3",
        default=False,
        action="store_true",
        help="Use POP3 instead of IMAP",
    )
    parser.add_argument("--user", "-u", required=True, type=str)
    parser.add_argument("--password", "-p", required=True)
    parser.add_argument(
        "--server", "-s", required=True, type=str, help="Mail server address"
    )
    parser.add_argument(
        "--valid",
        "-v",
        required=True,
        type=str,
        help="Valid sender emails, eg user@site.com",
        nargs="+",
    )
    parser.add_argument(
        "--match",
        "-m",
        required=True,
        type=str,
        help='Valid subject, eg "(.)* lims"',
        nargs="+",
    )
    parser.add_argument(
        "--file_path",
        "-fp",
        required=False,
        type=str,
        help="Path for saving files",
        nargs="+",
    )
    parser.add_argument(
        "--delete",
        "-d",
        default=False,
        action="store_true",
        help="Delete mail after saving",
    )
    parser.add_argument(
        "--ignore",
        "-i",
        default=False,
        action="store_true",
        help="Delete ignored mail after saving",
    )
    parser.add_argument(
        "--rename",
        "-r",
        default=False,
        action="store_true",
        help="Add timestamp to file",
    )
    parser.add_argument(
        "--inbox",
        "-ib",
        required=False,
        default=["INBOX"],
        type=str,
        help="Name of inbox (INBOX or processed)",
        nargs="+",
    )
    Xargs = parser.parse_args()

    logger.info(f"Start run with {Xargs}")
    if Xargs.pop3:
        process_pop3(Xargs)
    else:
        process_imap(Xargs)
    logger.info("Run complete")
