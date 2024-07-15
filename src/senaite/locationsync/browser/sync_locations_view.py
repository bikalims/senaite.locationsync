# -*- coding: utf-8 -*-

from bika.lims.api.mail import compose_email
from bika.lims.api.mail import send_email
from bika.lims import api as bika_api
from bika.lims.api import get_brain_by_uid
import csv
from DateTime import DateTime

# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText
# import json
import logging
import os
from plone.protect.interfaces import IDisableCSRFProtection
from Products.Five.browser import BrowserView
from Products.CMFPlone.utils import safe_unicode
from Products.statusmessages.interfaces import IStatusMessage
from senaite import api
from senaite.core import logger
from senaite.locationsync import _
import subprocess
import time

# from smtplib import SMTPRecipientsRefused
# from smtplib import SMTPServerDisconnected
import transaction
from zope.interface import Interface, alsoProvides

EMAIL_SUPER = True
COMMIT_COUNT = 100
FORCE_ABORT = False
SETUP_RUN = False

CR = "\n"
ACCOUNT_FILE_NAME = "Account lims.csv"
LOCATION_FILE_NAME = "location lims.csv"
SYSTEM_FILE_NAME = "system lims.csv"
CONTACT_FILE_NAME = "attention contact lims.csv"

ACCOUNT_FILE_HEADERS = ["Customer_Number", "Account_name", "Inactive", "On_HOLD"]
LOCATION_FILE_HEADERS = [
    "Customer_Number",
    "location_name",
    "Locations_id",
    "account_manager1",
    "street",
    "city",
    "state",
    "postcode",
    "branch",
    "Contract_Number",
    "HOLD",
    "Cancel_Box",
]
SYSTEM_FILE_HEADERS = [
    "Location_id",
    "Equipment_ID",
    "SystemID",
    "Equipment_Description2",
    "system_name",
    "Inactive_Retired_Flag",
    "system",
]
CONTACT_FILE_HEADERS = ["contactID", "Locations_id", "WS_Contact_Name", "email"]


class ISyncLocationsView(Interface):
    """Marker Interface for ISyncLocationsView"""


class SyncLocationsView(BrowserView):
    def __init__(self, context, request):
        super(SyncLocationsView, self).__init__(context, request)
        self.context = context
        self.request = request
        self.logs = []
        self.sync_base_folder = api.get_registry_record(
            "senaite.locationsync.location_sync_control_panel.sync_base_folder"
        )
        self.sync_current_folder = "{}/current".format(self.sync_base_folder)
        self.sync_archive_folder = "{}/archive".format(self.sync_base_folder)
        self.sync_error_folder = "{}/errors".format(self.sync_base_folder)
        self.sync_logs_folder = "{}/logs".format(self.sync_base_folder)
        self.sync_history_folder = "{}/all".format(self.sync_base_folder)

    def __call__(self):
        if EMAIL_SUPER and not self.supervisor_exists():
            msg = "Laboratory has no supervisor to email the results to. Assign one and try again"
            IStatusMessage(self.request).addStatusMessage(_(msg), "error")
            self.request.response.redirect(self.context.absolute_url())
            return
        no_abort = self.request.form.get("no-abort") is not None
        if self.request.form.get("commit", "false").lower() == "true":
            logger.info("Commit every 100 transactions")
            COMMIT_COUNT = 100
        else:
            logger.info("Only commit at the end of the run")
            COMMIT_COUNT = 0
        if self.request.form.get("get_emails", "true").lower() == "true":
            err_code = self.get_emails()
            if err_code is not None:
                msg = (
                    "Process cannot complete because it failed trying to get the emails with code "
                    + err_code
                )
                IStatusMessage(self.request).addStatusMessage(_(msg), "error")
                self.request.response.redirect(self.context.absolute_url())
                return
        else:
            logger.info("Do not get emaiuls")
        logger.info("SyncLocationsView: no_abort = {}".format(no_abort))
        if (
            self.sync_base_folder is None
            or len(self.sync_base_folder) == 0
            or not os.path.exists(self.sync_base_folder)
        ):
            msg = "Sync Base Folder value on Control Panel is not set correctly"
            IStatusMessage(self.request).addStatusMessage(_(msg), "error")
            self.request.response.redirect(self.context.absolute_url())
            return

        msg = "Location syncronization could take some time so the results will be emailed when complete"
        IStatusMessage(self.request).addStatusMessage(_(msg), "info")
        self.request.response.redirect(self.context.absolute_url())

        # disable CSRF because
        alsoProvides(self.request, IDisableCSRFProtection)
        self.sync_locations()
        errors = [l for l in self.logs if l["level"].lower() == "error"]
        warnings = [l for l in self.logs if l["level"].lower() == "warn"]
        actions = [l for l in self.logs if l["action"] != "Info"]
        additions = [l for l in actions if l["action"] == "Added"]
        self.log(
            "Stats: found {} errors, {} warnings and {} actions ({} additions)".format(
                len(errors), len(warnings), len(actions), len(additions)
            )
        )
        # Move data files
        if len(errors) == 0:
            self._move_file(ACCOUNT_FILE_NAME, self.sync_archive_folder)
            self._move_file(LOCATION_FILE_NAME, self.sync_archive_folder)
            self._move_file(SYSTEM_FILE_NAME, self.sync_archive_folder)
            self._move_file(CONTACT_FILE_NAME, self.sync_archive_folder)
        else:
            self._move_file(ACCOUNT_FILE_NAME, self.sync_error_folder)
            self._move_file(LOCATION_FILE_NAME, self.sync_error_folder)
            self._move_file(SYSTEM_FILE_NAME, self.sync_error_folder)
            self._move_file(CONTACT_FILE_NAME, self.sync_error_folder)
            if not no_abort:
                self.log("Abort all transactions because errors we found")
                transaction.abort()

        # Create log file
        log_file_name = self.write_log_file()

        # Send email
        if EMAIL_SUPER:
            self.email_logs(log_file_name)
        else:
            logger.info("skip supervisory email requested")

        if FORCE_ABORT:
            logger.info("Force abort requested")
            transaction.abort()

        # return the concatenated logs
        return CR.join(
            [
                "{} {:10} {}".format(l["time"], str(l["action"]), l["message"])
                for l in self.logs
            ]
        )

    def get_emails(self):
        logger.info("Get emails")
        # python get_email.py --user zzzz --server pop.zzzz.com --pop3 --password zzzz --valid NoReply@zzzz.com.zzzz --match '.* lims' --file_path '/home/zzzz/sync/current'
        cmd_path = self.sync_base_folder + "/bin/get_email.py"
        file_path = self.sync_base_folder + "/current"
        cmds = [
            "python3",
            cmd_path,
            "--user",
            api.get_registry_record(
                "senaite.locationsync.location_sync_control_panel.sync_email_user"
            ),
            "--password",
            api.get_registry_record(
                "senaite.locationsync.location_sync_control_panel.sync_email_password"
            ),
            "--server",
            "imap.bikalabs.com",
            "--match",
            api.get_registry_record(
                "senaite.locationsync.location_sync_control_panel.sync_email_allowed_subjects"
            ),
            "--file_path",
            file_path,
            "--delete",
        ]
        valid_emails = api.get_registry_record(
            "senaite.locationsync.location_sync_control_panel.sync_email_allowed_emails"
        ).split(",")
        if valid_emails:
            cmds.append("--valid")
            cmds.extend(valid_emails)
        logger.info("get_emails: commands = {}".format(cmds))
        try:
            subprocess.check_call(cmds)
            time.sleep(10)
        except subprocess.CalledProcessError as err:
            err_code = str(err.returncode)
            logger.error("get_emails failed with error code {}".format(err_code))
            return err_code

    def supervisor_exists(self):
        lab = api.get_setup().laboratory
        supervisor = lab.getSupervisor()
        if supervisor:
            return True
        else:
            return False

    def email_logs(self, log_file_name):
        if not self.supervisor_exists():
            return
        recipients = api.get_registry_record(
            "senaite.locationsync.location_sync_control_panel.sync_dest_emails"
        )
        if recipients:
            recipients = recipients.split(',')
        else:
            recipients = []
        lab = api.get_setup().laboratory
        supervisor = lab.getSupervisor()
        super_name = safe_unicode(supervisor.getFullname()).encode("utf-8")
        super_email = safe_unicode(supervisor.getEmailAddress()).encode("utf-8")
        recipients.append(super_email)
        timestamp = DateTime.strftime(DateTime(), "%Y-%m-%d %H:%M")
        # site_name = self.context.getPhysicalPath()[1]
        # if site_name not in self.context.absolute_url():
        #     site_name is None
        log_file_url = "{}/@@get_log_file?name={}".format(
            self.context.absolute_url(), log_file_name
        )
        # if site_name is not None:
        #     log_file_url = "/{}/@@get_log_file?name={}".format(site_name, log_file_name)
        log_dir_url = "{}/log_file_view".format(
            self.context.absolute_url()
        )
        data_dir_url = "{}/data_file_view".format(
            self.context.absolute_url()
        )
        errors = [l for l in self.logs if l["level"].lower() == "error"]
        warnings = [l for l in self.logs if l["level"].lower() == "warn"]
        created = [l for l in self.logs if l["action"] == "Created"]
        additions = [l for l in self.logs if l["action"] == "Added"]
        email_body = """
        Hi {},

        The location syncronization run completed at {} with:
            * {} errors
            * {} warnings
            * {} creations
            * {} additions
        
        The log file can be found here {}
        And the history of log files can be found here: {}
        Remember that all the data files used in the sync can be found here: {}

        Regards,
        """.format(
            super_name, timestamp, len(errors), len(warnings), len(created), len(additions), log_file_url, log_dir_url, data_dir_url
        )
        subject = "Location syncronization completed with no errors"
        if len(errors) > 0:
            subject = "Location syncronization completed with {} errors".format(len(errors))
        # HACK!!!!!!
        recipients=['mike@metcalfe.co.za',]
        logger.info("Send sync results to {}".format(recipients))
        from_addr = lab.getEmailAddress()
        # HACK!!!!!!
        from_addr = 'mike@webtide.co.za'
        logger.info("Send sync results from {}".format(from_addr))
        email = compose_email(
            from_addr=from_addr,
            to_addr=recipients,
            subj=subject,
            body=email_body,
            attachments=[],
        )
        if email:
            send_email(email)

    def _all_folder_exist(self):
        success = True
        if not os.path.exists(self.sync_base_folder):
            self.log(
                "Sync Base Folder {} does not exist".format(self.sync_base_folder),
                level="error",
            )
            success = False
        if not os.path.exists(self.sync_current_folder):
            self.log(
                "Sync Current Folder {} does not exist".format(
                    self.sync_current_folder
                ),
                level="error",
            )
            success = False
        if not os.path.exists(self.sync_archive_folder):
            self.log(
                "Sync Archive Folder {} does not exist".format(
                    self.sync_archive_folder
                ),
                level="error",
            )
            success = False
        if not os.path.exists(self.sync_error_folder):
            self.log(
                "Sync Error Folder {} does not exist".format(self.sync_error_folder),
                level="error",
            )
            success = False
        if not os.path.exists(self.sync_logs_folder):
            self.log(
                "Sync Error Folder {} does not exist".format(self.sync_logs_folder),
                level="error",
            )
            success = False
        return success

    def log(self, message, context="Main", level="info", action=False):
        """Log to logging facility

        :param message: Log message
        :param level: Log level, e.g. debug, info, warning, error
        """
        if action is True:
            action = "TakeAction"
        else:
            if action is False:
                action = "Info"
            if level == "error":
                action = "FaultFound"

        # log into default facility
        log_level = logging.getLevelName(level.upper())
        logger.log(level=log_level, msg=message)

        # Append to logs
        timestamp = DateTime.strftime(DateTime(), "%Y-%m-%d %H:%M:%S")
        self.logs.append(
            {
                "time": timestamp,
                "level": "{}{}".format(level[0].upper(), level[1:].lower()),
                "context": context,
                "action": action,
                "message": message,
            }
        )

    def sync_locations(self):
        if not self._all_folder_exist():
            return
        self.log("Folder check was successful")

        self.log("Sync process started")
        self.process_file("Accounts", ACCOUNT_FILE_NAME, ACCOUNT_FILE_HEADERS)
        self.process_file("Locations", LOCATION_FILE_NAME, LOCATION_FILE_HEADERS)
        self.process_file("Systems", SYSTEM_FILE_NAME, SYSTEM_FILE_HEADERS)
        self.process_file("Contacts", CONTACT_FILE_NAME, CONTACT_FILE_HEADERS)
        self.log("Sync process completed")

    def process_file(self, file_type, file_name, headers=[]):
        data = self.read_file_data(file_type, file_name, headers=headers)
        if "FileNotFound" in data.get("errors", []):
            return

        self.log(
            "Found {} rows in {} with {} errros".format(
                len(data["rows"]),
                file_name,
                len(data["errors"]),
            ),
            context=file_type,
        )
        if data.get("errors", []):
            return

        # Process Rules
        if file_type == "Accounts":
            self.process_account_rules(data)
        elif file_type == "Locations":
            self.process_locations_rules(data)
        elif file_type == "Systems":
            self.process_systems_rules(data)
        elif file_type == "Contacts":
            self.process_contacts_rules(data)
        if COMMIT_COUNT > 0:
            transaction.commit()

    def clean_row(self, row):
        illegal_chars = ["\xef\xbb\xbf", "\xa0", u"\u2019"]
        cleaned = []
        for cell in row:
            cell = cell.strip()
            cell = safe_unicode(cell).encode("utf-8")
            new = ""
            for char in cell:
                if ord(char) > 128:
                    continue
                if char in illegal_chars:
                    continue
                new += char
            cleaned.append(new)
        return cleaned

    def write_log_file(self):
        timestamp = DateTime.strftime(DateTime(), "%Y%m%d-%H%M-%S")
        # TODO for testing timestamp = "aaa"
        file_name = "SyncLog-{}.csv".format(timestamp)
        logger.info("Write log file {}".format(file_name))
        file_path = "{}/{}".format(self.sync_logs_folder, file_name)

        with open(file_path, "w") as f:
            writer = csv.writer(f)
            writer.writerow(["Time", "Context", "Action", "Level", "Message"])
            for log in self.logs:
                row = [
                    log["time"],
                    log["context"],
                    log["action"],
                    log["level"],
                    log["message"],
                ]
                writer.writerow(row)
        logger.info("Log file placed here {}".format(file_path))
        return file_name

    def read_file_data(self, file_type, file_name, headers):
        # self.log("Get {} data file started".format(file_type))
        file_path = "{}/{}".format(self.sync_current_folder, file_name)
        if not os.path.exists(file_path):
            self.log(
                "{} file not found".format(file_type), context=file_type, level="error"
            )
            return {"headers": [], "rows": [], "errors": ["FileNotFound"]}

        rows = []
        errors = []
        with open(file_path) as csvfile:
            reader = csv.reader(csvfile, delimiter=",", quotechar='"')
            for i, row in enumerate(reader):
                if len(row) == 0:
                    continue
                row = self.clean_row(row)
                if i == 0:
                    if len(headers) != len(row):
                        msg = "File {} has incorrect number of headers: found {}, it must be {}".format(
                            file_name, len(row), len(headers)
                        )
                        self.log(msg, context=file_type, level="error")
                        errors.append(msg)
                        break
                    if headers != row:
                        msg = "File {} has incorrect headers: found [{}], it must be [{}]".format(
                            file_name, ", ".join(row), ", ".join(headers)
                        )
                        self.log(msg, context=file_type, level="error")
                        errors.append(msg)
                        break
                    self.log(
                        "File {} with correct {} header columns".format(
                            file_name, len(row), context=file_type
                        ),
                        context=file_type,
                    )
                    continue
                if len(headers) != len(row):
                    msg = "File {} incorrect number of columns {} in row {}".format(
                        file_name,
                        len(row),
                        i,
                    )
                    errors.append(msg)
                    continue
                # Process cells in row
                adict = {}
                for idx, cell in enumerate(row):
                    try:
                        val = row[idx].decode("utf-8", "strict")
                    except UnicodeDecodeError:
                        self.log(
                            "Error on row {} of file {} because of decoding of value {} in field {}. But offending characters have been replaced with spaces".format(
                                i,
                                file_name,
                                row[idx],
                                headers[idx],
                            ),
                            context=file_type,
                            level="warn",
                        )
                        val = (
                            row[idx].decode("utf-8", "replace").replace(u"\ufffd", " ")
                        )
                    adict[headers[idx]] = val
                rows.append(adict)
                # self.log("File {} row {}: {}".format(file_name, i, ", ".join(row)))
        self.log("Read {} data file complete".format(file_type), context=file_type)
        return {"headers": headers, "rows": rows, "errors": errors}

    def _move_file(self, file_name, dest_folder):
        from_file_path = "{}/{}".format(self.sync_current_folder, file_name)
        if not os.path.exists(from_file_path):
            self.log(
                "Cannot move file {} because it's not found".format(from_file_path),
                context="MoveFiles",
                level="error",
            )
            return
        if os.path.exists(from_file_path):
            file_name = ".".join(file_name.split(".")[:-1])
            timestamp = DateTime.strftime(DateTime(), "%Y%m%d.%H%M")
            to_file_path = "{}/{}.{}.csv".format(dest_folder, file_name, timestamp)
            os.rename(from_file_path, to_file_path)
            self.log(
                "Moved file {} to {} folder".format(file_name, dest_folder),
                context="MoveFiles",
            )
            return
        dest_file_path = "{}/{}".format(dest_folder, file_name)
        if os.path.exists(dest_file_path):
            self.log(
                "Cannot move file {} because it's already in {} folder".format(
                    file_name, dest_folder
                ),
                context="MoveFiles",
            )
            return
        self.log(
            "Cannot move file {}".format(file_name), context="MoveFiles", level="error"
        )

    def process_account_rules(self, data):
        portal = api.get_portal()

        # Prep clients
        clients = bika_api.search({
                "portal_type": "Client"
            },
            catalog="senaite_catalog_client"
        )
        client_ids = [c["getClientID"] for c in clients]
        num_rows = len(data["rows"])
        for i, row in enumerate(data["rows"]):
            if COMMIT_COUNT > 0 and i % COMMIT_COUNT == 0:
                transaction.commit()
            logger.info("Process row {} of {} from Accounts file".format(i, num_rows))
            if len(row.get("Customer_Number", "")) == 0:
                self.log(
                    "Row {} of Account file has no Customer_Number value".format(i),
                    context="Accounts",
                    level="error",
                )
                continue
            if SETUP_RUN and (row["Inactive"] == "1" or row["On_HOLD"] == "1"):
                self.log(
                    "Row {} of Contact file is inactive so has been ignored in this setup run".format(
                        i
                    ),
                    context="Accounts",
                    level="info",
                )
                continue
            if row["Customer_Number"] in client_ids:
                # Client Already Exists
                client = [
                    c for c in clients if row["Customer_Number"] == c["getClientID"]
                ][0]
                self.log("Found Client {} ({})".format(row["Account_name"], row["Customer_Number"]), context="Accounts")
                current_state = api.get_workflow_status_of(client)
                if row["Inactive"] == "1" or row["On_HOLD"] == "1":
                    if current_state == "inactive":
                        self.log(
                            "Client {} already inactive".format(row["Account_name"]),
                            context="Accounts",
                        )
                    else:
                        api.do_transition_for(client, "deactivate")
                        self.log(
                            "Deactivated Client {}".format(row["Account_name"]),
                            context="Accounts",
                            action="Deactivated",
                        )
                else:
                    # marked in file as active
                    if current_state == "inactive":
                        api.do_transition_for(client, "activate")
                        self.log(
                            "Activated Client {}".format(row["Account_name"]),
                            context="Accounts",
                            action="Activated",
                        )
                    if client.Title != row["Account_name"]:
                        client = api.get_object(client)
                        self.log(
                            "Rename Client '{}' title to {}".format(
                                client.Title(), row["Account_name"]
                            ),
                            context="Accounts",
                            action="Renamed",
                        )
                        client.setTitle(row["Account_name"])
                        client.reindexObject()
            else:
                # Client not in DB
                client = bika_api.create(
                    portal.clients,
                    "Client",
                    ClientID=row["Customer_Number"],
                    title=row["Account_name"],
                )

                self.log(
                    "Created Client {}".format(row["Account_name"]),
                    action="Created",
                    context="Accounts",
                )
                if row["Inactive"] == "1" or row["On_HOLD"] == "1":
                    api.do_transition_for(client, "deactivate")
                    self.log(
                        "Deactivate newly created client {}".format(
                            row["Account_name"]
                        ),
                        context="Accounts",
                        action="Deactivated",
                    )
        return True

    def process_locations_rules(self, data):
        portal = api.get_portal()

        # Prep lab_contacts
        lab_contacts_folder = portal.bika_setup.bika_labcontacts
        lab_contact_names = []
        lab_contacts = []
        for contact in lab_contacts_folder.values():
            lab_contacts.append(contact)
            contact_title = contact.Title().strip("--- ")
            lab_contact_names.append(contact_title)

        # Prep clients
        clients = bika_api.search({
                "portal_type": "Client"
            },
            catalog="senaite_catalog_client"
        )
        client_ids = [c["getClientID"] for c in clients]
        num_rows = len(data["rows"])
        for i, row in enumerate(data["rows"]):
            if COMMIT_COUNT > 0 and i % COMMIT_COUNT == 0:
                transaction.commit()
            logger.info("Process row {} of {} from Locations file".format(i, num_rows))
            if SETUP_RUN and (row["HOLD"] == "1" or row["Cancel_Box"] == "1"):
                self.log(
                    "Row {} of Locations file is on hold so has been ignored in this setup run".format(
                        i
                    ),
                    context="Locations",
                    level="info",
                )
                continue
            # field validation - required fields
            if len(row.get("Customer_Number", "")) == 0:
                self.log(
                    "Row {} of Locations file has no Customer_Number value".format(i),
                    context="Locations",
                    level="error",
                )
                continue
            if len(row.get("Locations_id", "")) == 0:
                self.log(
                    "Row {} of Locations file has no Locations_id value".format(i),
                    context="Locations",
                    level="error",
                )
                continue
            # field validation - client must exist
            if row["Customer_Number"] not in client_ids:
                self.log(
                    "Client ID {} on row {} of the locations file was not found in DB".format(
                        row["Customer_Number"], i
                    ),
                    context="Locations",
                    level="warn",
                )
                continue
            client = [c for c in clients if row["Customer_Number"] == c["getClientID"]][
                0
            ]
            self.log("Found Client {} ({})".format(client.Title, row["Customer_Number"]), context="Locations")

            locations = bika_api.search(
                {
                    "portal_type": "SamplePointLocation",
                    "path": {"query": client.getPath()},
                    "getSamplePointLocationID": row["Locations_id"],
                },
                catalog="senaite_catalog_setup"
            )
            location = None
            if locations:
                # Location exists
                location_brain = locations[0]
                # If row['HOLD'] or row['Cancel_Box'], see code below
                # If row['account_manager1'], see code below
                # For address field in row, see code below
                self.log(
                    "Found location {}".format(row["Locations_id"]), context="Locations"
                )
            else:
                # Location does NOT exist
                client_obj = api.get_object(client)
                title = row["location_name"]
                location = bika_api.create(
                    client_obj,
                    "SamplePointLocation",
                    title=title,
                    # sample_point_location_id=row["Locations_id"],
                )
                location.setSamplePointLocationID(row["Locations_id"])
                client_path = "/".join(client_obj.getPhysicalPath())
                location_path = "/".join(location.getPhysicalPath())
                self.log(
                    "Created location {} in Client {} at {}".format(
                        title, client.Title, client_path
                    ),
                    context="Locations",
                    action="Created",
                )
                location_brain = get_brain_by_uid(location.UID())
                if not location_brain:
                    self.log(
                        "Failed to find newly created location {} and client {}".format(
                            title,
                            client.Title,
                        ),
                        context="Locations",
                        level="error",
                        action="ReportToSysAdmin",
                        )
                    continue
                else:
                    self.log(
                        "Found newly created location {} and client {}".format(
                            location_brain.Title,
                            client.Title,
                        ),
                        context="Locations",
                        level="info",
                        )


            # Rules for if location existed or has just been created
            if row["HOLD"] == "1" or row["Cancel_Box"] == "1":
                # deactivate location and children
                current_state = 'active'
                if hasattr(location_brain, 'review_state'):
                    current_state = location_brain.review_state
                if current_state == "active":
                    if location is None:
                        location = api.get_object(location_brain)
                    api.do_transition_for(location, "deactivate")
                    self.log(
                        "Location {} in Client {} has been deactivated".format(
                            location_brain.Title, client.Title
                        ),
                        context="Locations",
                        action="Deactivated",
                    )
                systems = bika_api.search(
                    {
                        "portal_type": "SamplePoint",
                        "path": {"query": location_brain.getPath()},
                    },
                    catalog="senaite_catalog_setup"
                )
                for system in systems:
                    if system.review_state == "active":
                        system = api.get_object(system)
                        api.do_transition_for(system, "deactivate")
                        self.log(
                            "System {} in Location {} in Client {} has been deactivated".format(
                                system.Title(), location_brain.Title, client.Title
                            ),
                            context="Locations",
                            action="Deactivated",
                        )
            if row["account_manager1"]:
                if row["account_manager1"] in lab_contact_names:
                    contact = [
                        c
                        for c in lab_contacts
                        if row["account_manager1"] == c.Title().strip("--- ")
                    ][0]
                    self.log(
                        "Found lab contact {} for Location {}".format(
                            contact.Title(), location_brain.Title
                        ),
                        context="Locations",
                    )
                else:
                    firstname = " ".join(row["account_manager1"].split(" ")[:-1])
                    if len(firstname) == 0:
                        firstname = "---"
                    surname = row["account_manager1"].split(" ")[-1]
                    try:
                        contact = bika_api.create(
                            lab_contacts_folder,
                            "LabContact",
                            Surname=surname,
                            Firstname=firstname,
                        )
                    except Exception:
                        self.log(
                            "Failed creating Lab Contact {} for location {} and client {}".format(
                                contact.Title(),
                                location_brain.Title,
                                client.Title,
                            ),
                            context="Locations",
                            level="error",
                            action="ReportToSysAdmin",
                        )
                        continue

                    lab_contacts.append(contact)
                    contact_title = contact.Title().strip("--- ")
                    lab_contact_names.append(contact_title)
                    self.log(
                        "Created a Lab Contact {} for location {} and client {}".format(
                            contact.Title(), location_brain.Title, client.Title
                        ),
                        context="Locations",
                        action="Created",
                    )
                    # TODO Notify lab admin that new lab contact created with no email
                contacts = None
                if hasattr(location_brain, 'getAccountManagers'):
                    contacts = location_brain.getAccountManagers
                if contacts is None:
                    contacts = []
                if contact.UID() not in contacts:
                    contacts.append(contact.UID())
                    if location is None:
                        location = api.get_object(location_brain)
                    location.setAccountManagers(contacts)
                    self.log(
                        "Added Lab Contact {} to location {} and client {}".format(
                            contact.Title(), location_brain.Title, client.Title
                        ),
                        context="Locations",
                        action="Added",
                    )
                # Get address from row and update location, new or old
                address = self._get_address_field(row, row_num=i)
                if address:
                    if location is None:
                        location = api.get_object(location_brain)
                    old_address = location.getAddress()
                    if [address] != old_address:
                        location.setAddress([address])
                        self.log(
                            "Changed Address to location {} and client {} from {} to {}".format(
                                location_brain.Title, client.Title, old_address, address
                            ),
                            context="Locations",
                            action="Added",
                        )

        return True

    def process_systems_rules(self, data):
        locations = bika_api.search({
                "portal_type": "SamplePointLocation"
            },
            catalog="senaite_catalog_setup"
        )
        location_ids = [l.getSamplePointLocationID for l in locations]
        num_rows = len(data["rows"])
        for i, row in enumerate(data["rows"]):
            if COMMIT_COUNT > 0 and i % COMMIT_COUNT == 0:
                transaction.commit()
            logger.info("Process row {} of {} from Systems file".format(i, num_rows))
            if SETUP_RUN and row["Inactive_Retired_Flag"] == "1":
                self.log(
                    "Row {} of System file is on hold so has been ignored in this setup run".format(
                        i
                    ),
                    context="Systems",
                    level="info",
                )
                continue
            # field validation - required fields
            if len(row.get("SystemID", "")) == 0:
                self.log(
                    "System on row {} with name {} in location {} has no SystemID field".format(
                        i,
                        row.get("system_name", "missing"),
                        row.get("Location_id", "missing"),
                    ),
                    context="Systems",
                    level="error",
                )
                continue
            if row["Location_id"] not in location_ids:
                msg = "Location {} on row {} in systems file not found in DB".format(
                    row["Location_id"], i
                )
                self.log(msg, level="warn", context="Systems")
                continue
            location = None
            location_brain = [
                l for l in locations if row["Location_id"] == l.getSamplePointLocationID
            ][0]
            self.log("Found Location {}".format(row["Location_id"]), context="Systems")
            systems = bika_api.search(
                {
                    "portal_type": "SamplePoint",
                    "path": {"query": location_brain.getPath()},
                    "getSamplePointID": row["SystemID"],
                },
                catalog="senaite_catalog_setup"
            )
            reindex = False
            if len(systems) > 0:
                system = api.get_object(systems[0])
                self.log(
                    "Found System {} with ID {} in Location {}".format(
                        system.Title(), row["SystemID"], location_brain.Title
                    ),
                    context="Systems",
                )
                if row["Inactive_Retired_Flag"] == "1":
                    if api.get_workflow_status_of(system) == "active":
                        self.log(
                            "Deactivate System {} in location {} beacuse it's marked as Inactive_Retired_Flag".format(
                                row["system_name"], location_brain.Title
                            ),
                            context="Systems",
                            action="Deactivated",
                        )
                        api.do_transition_for(system, "deactivate")
            else:
                # Create new system
                if row["Inactive_Retired_Flag"] == "1":
                    self.log(
                        "System {} in location {} doesn't exists but is marked as Inactive_Retired_Flag".format(
                            row["system_name"], location_brain.Title
                        ),
                        context="Systems",
                    )
                    continue
                if location is None:
                    location = api.get_object(location_brain)
                system = bika_api.create(
                    location,
                    "SamplePoint",
                    title=row["system_name"],
                )
                system.SamplePointId = row["SystemID"]
                reindex = True
                client_title = location.aq_parent.Title()
                self.log(
                    "Created system {} in location {} in client {}".format(
                        system.Title(), location_brain.Title, client_title
                    ),
                    context="Systems",
                    action="Created",
                )
            if system.EquipmentID != row["Equipment_ID"]:
                system.EquipmentID = row["Equipment_ID"]
                reindex = True
            if system.EquipmentType != row["system"]:
                reindex = True
                system.EquipmentType = row["system"]
            if system.EquipmentDescription != row["Equipment_Description2"]:
                reindex = True
                system.EquipmentDescription = row["Equipment_Description2"]
            if reindex:
                system.reindexObject()

        return True

    def process_contacts_rules(self, data):
        locations = api.search({
                "portal_type": "SamplePointLocation"
            },
            catalog="senaite_catalog_setup"
        )
        locations = [api.get_object(l) for l in locations]
        location_ids = [l.getSamplePointLocationID() for l in locations]
        num_rows = len(data["rows"])
        for i, row in enumerate(data["rows"]):
            if COMMIT_COUNT > 0 and i % COMMIT_COUNT == 0:
                transaction.commit()
            logger.info("Process row {} of {} from Contacts file".format(i, num_rows))
            if len(row.get("contactID", "")) == 0:
                self.log(
                    "Contact on row {} in location {} has no contactID field".format(
                        i, row.get("Locations_id", "missing")
                    ),
                    context="Contacts",
                    level="error",
                )
                continue
            if len(row.get("Locations_id", "")) == 0:
                self.log(
                    "Contact on row {} with contactID {} has no Locations_id field".format(
                        i, row.get("contactID", "missing")
                    ),
                    context="Contacts",
                    level="error",
                )
                continue
            if row["Locations_id"] not in location_ids:
                msg = "Location {} on row {} in contacts file not found in DB".format(
                    row["Locations_id"], i
                )
                self.log(msg, level="warn", context="Contacts")
                continue

            self.log(
                "Found Location {}".format(row["Locations_id"]), context="Contacts"
            )
            location = [
                l
                for l in locations
                if row["Locations_id"] == l.getSamplePointLocationID()
            ][0]
            location = api.get_object(location)
            client = location.aq_parent
            if client.portal_type != "Client":
                raise RuntimeError(
                    "Location {} in {} is not inside a client".format(
                        location.Title(), location.absolute_url()
                    )
                )
            contacts = client.getContacts()
            found = False
            for contact in contacts:
                contact_email = contact.getEmailAddress()
                if contact_email and row["email"] == contact_email:
                    self.log(
                        "Found contact with email {} in location {}".format(
                            row["email"], location.Title()
                        ),
                        context="Contacts",
                    )
                    found = True
                    break

            if found:
                continue

            firstname = "--"
            surname = "Unknown"
            if len(row.get("WS_Contact_Name", "")) > 0:
                firstname = " ".join(row["WS_Contact_Name"].split(" ")[:-1])
                if len(firstname) == 0:
                    firstname = "---"
                surname = row["WS_Contact_Name"].split(" ")[-1]
            contact = bika_api.create(
                client,
                "Contact",
            )
            contact.Firstname = firstname
            contact.Surname = surname
            contact.ContactId = row["contactID"]
            contact.setEmailAddress(row["email"])
            self.log(
                "Created contact with email {} for location {} in client {}".format(
                    contact.getEmailAddress(), location.Title(), client.Title()
                ),
                context="Contacts",
                action="Created",
            )
            transaction.commit()
        return True

    def _get_address_field(self, row, row_num):
        state = row.get("state", "")
        if len(state) == 0:
            pass
        state_vocab = {
            "VIC": "Victoria",
            "SA": "South Australia",
            "WA": "Western Australia",
            "QLD": "Queensland",
            "TAS": "Tasmania",
            "NSW": "New South Wales",
            "NT": "Northern Territory",
            "ACT": "Australia Capital Territory",
        }
        if state not in state_vocab:
            self.log(
                "Unknown state abbreviation {} on row {} of the locations file".format(
                    state, row_num
                ),
                context="Locations",
                level="warn",
            )
            div1 = state
        else:
            div1 = state_vocab[state]
        address = {
            "address": row.get("street", ""),
            "city": row.get("city", ""),
            "country": "Australia",
            "subdivision1": div1,
            "subdivision2": "",
            "type": "physical",
            "zip": row.get("postcode", ""),
        }
        return address

    def create(self, container, portal_type, *args, **kwargs):
        from bika.lims.utils import tmpID

        # from zope.component import getUtility
        # from zope.event import notify
        # from zope.lifecycleevent import ObjectCreatedEvent
        from Products.CMFPlone.utils import _createObjectByType

        # from zope.lifecycleevent import modified
        # from zope.component.interfaces import IFactory

        if kwargs.get("title") is None:
            kwargs["title"] = "New {}".format(portal_type)

        # generate a temporary ID
        tmp_id = tmpID()

        obj = _createObjectByType(portal_type, container, tmp_id)

        # # handle AT Content
        # if is_at_content(obj):
        #     obj.processForm()

        # Edit after processForm; processForm does AT unmarkCreationFlag.
        obj.edit(**kwargs)

        # # explicit notification
        # modified(obj)
        return obj
