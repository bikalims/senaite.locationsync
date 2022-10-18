# -*- coding: utf-8 -*-

import csv
from DateTime import DateTime
import logging
import os
from plone.protect.interfaces import IDisableCSRFProtection
from senaite import api
from senaite.core import logger
from zope.interface import alsoProvides
from Products.Five.browser import BrowserView
from zope.interface import Interface

CR = "\n"
SYNC_BASE_FOLDER = "/home/mike/sync"
SYNC_CURRENT_FOLDER = "{}/current".format(SYNC_BASE_FOLDER)
SYNC_ARCHIVE_FOLDER = "{}/archive".format(SYNC_BASE_FOLDER)
SYNC_ERROR_FOLDER = "{}/errors".format(SYNC_BASE_FOLDER)

ACCOUNT_FILE_NAME = "Account lims.csv"
LOCATION_FILE_NAME = "location lims.csv"
SYSTEM_FILE_NAME = "system lims.csv"
CONTACT_FILE_NAME = "attention contact lims.csv"

EMAIL_ADDRESS = "mike@webtide.co.za"

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

    def __call__(self):
        # disable CSRF because
        alsoProvides(self.request, IDisableCSRFProtection)
        # run syncronisation
        success = self.sync_locations()
        if not success:
            # Send email
            # TODO
            pass
        # return the concatenated logs
        return CR.join(self.logs)

    def _all_folder_exist(self):
        success = True
        if not os.path.exists(SYNC_BASE_FOLDER):
            self.log(
                "Sync Base Folder {} does not exist".format(SYNC_BASE_FOLDER),
                level="error",
            )
            success = False
        if not os.path.exists(SYNC_CURRENT_FOLDER):
            self.log(
                "Sync Current Folder {} does not exist".format(SYNC_CURRENT_FOLDER),
                level="error",
            )
            success = False
        if not os.path.exists(SYNC_ARCHIVE_FOLDER):
            self.log(
                "Sync Archive Folder {} does not exist".format(SYNC_ARCHIVE_FOLDER),
                level="error",
            )
            success = False
        if not os.path.exists(SYNC_ERROR_FOLDER):
            self.log(
                "Sync Error Folder {} does not exist".format(SYNC_ERROR_FOLDER),
                level="error",
            )
            success = False
        return success

    def log(self, message, level="info", action=False):
        """Log to logging facility

        :param message: Log message
        :param level: Log level, e.g. debug, info, warning, error
        """
        if action:
            message = "Action: {}".format(message)

        # log into default facility
        log_level = logging.getLevelName(level.upper())
        logger.log(level=log_level, msg=message)

        # Append to logs
        timestamp = DateTime.strftime(DateTime(), "%Y-%m-%d %H:%M:%S")
        self.logs.append("{}, {}, {}".format(timestamp, log_level, message))

    def sync_locations(self):
        if not self._all_folder_exist():
            return False
        self.log("Folder check was successful")

        self.log("Sync process starting")
        self.process_file("Accounts", ACCOUNT_FILE_NAME, ACCOUNT_FILE_HEADERS)
        self.process_file("Locations", LOCATION_FILE_NAME, LOCATION_FILE_HEADERS)
        self.process_file("Systems", SYSTEM_FILE_NAME, SYSTEM_FILE_HEADERS)
        self.process_file("Contacts", CONTACT_FILE_NAME, CONTACT_FILE_HEADERS)
        self.log("Sync process complete")

    def process_file(self, file_type, file_name, headers=[]):
        data = self.read_file_data(file_type, file_name, headers=headers)
        self.log(
            "Found {} rows in {} with {} errros".format(
                len(data["rows"]),
                file_name,
                len(data["errors"]),
            )
        )
        if "FileNotFound" in data.get("errors", []):
            return

        if data.get("errors", []):
            self._move_file(file_name, SYNC_ERROR_FOLDER)
            return

        # TODO Process Rules
        success = False
        if file_type == "Accounts":
            success = self.process_account_rules(data)
        elif file_type == "Locations":
            success = self.process_locations_rules(data)
        elif file_type == "Systems":
            success = self.process_systems_rules(data)
        elif file_type == "Contacts":
            success = self.process_contacts_rules(data)

        # Move data file
        if success:
            self._move_file(file_name, SYNC_ARCHIVE_FOLDER)
        else:
            self._move_file(file_name, SYNC_ERROR_FOLDER)

    def clean_row(self, row):
        illegal_chars = ["\xef\xbb\xbf"]
        cleaned = []
        for cell in row:
            cell = cell.strip()
            for char in illegal_chars:
                if char in cell:
                    cell = cell.replace(char, "")
            cleaned.append(cell)
        return cleaned

    def read_file_data(self, file_type, file_name, headers):
        self.log("Read {} data file starting".format(file_type))
        file_path = "{}/{}".format(SYNC_CURRENT_FOLDER, file_name)
        if not os.path.exists(file_path):
            self.log("{} file not found".format(file_type), level="error")
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
                        self.log(msg, level="error")
                        errors.append(msg)
                        break
                    if headers != row:
                        msg = "File {} has incorrect headers: found [{}], it must be [{}]".format(
                            file_name, ", ".join(row), ", ".join(headers)
                        )
                        self.log(msg, level="error")
                        errors.append(msg)
                        break
                    self.log(
                        "File {} with corrent {} header columns".format(
                            file_name, len(row)
                        )
                    )
                    continue
                if len(headers) != len(row):
                    msg = "File {} incorrect number of columns {} in row {}: {}".format(
                        file_name, len(row), i, ", ".join(row)
                    )
                    errors.append(msg)
                    self.log(msg, level="error")
                    continue
                # Process cells in row
                adict = {}
                for idx, cell in enumerate(row):
                    adict[headers[idx]] = row[idx]
                rows.append(adict)
                # self.log("File {} row {}: {}".format(file_name, i, ", ".join(row)))
        self.log("Read {} data file complete".format(file_type))
        return {"headers": headers, "rows": rows, "errors": errors}

    def _move_file(self, file_name, dest_folder):
        from_file_path = "{}/{}".format(SYNC_CURRENT_FOLDER, file_name)
        to_file_path = "{}/{}".format(dest_folder, file_name)
        os.rename(from_file_path, to_file_path)

    def process_account_rules(self, data):
        portal = api.get_portal()
        clients = api.search({"portal_type": "Client"})
        client_ids = [c["getClientID"] for c in clients]
        for row in data["rows"]:
            if row["Customer_Number"] in client_ids:
                # Client Already Exists
                client = [
                    c for c in clients if row["Customer_Number"] == c["getClientID"]
                ][0]
                self.log("Found Client {}".format(row["Account_name"]))
                current_state = api.get_workflow_status_of(client)
                if row["Inactive"] == "1" or row["On_HOLD"] == "1":
                    if current_state == "inactive":
                        self.log(
                            "Client {} already inactive".format(row["Account_name"])
                        )
                        continue
                    else:
                        api.do_transition_for(client, "deactivate")
                        self.log(
                            "Deactivate Client {}".format(row["Account_name"]),
                            action=True,
                        )
                else:
                    # Marked in file as active
                    if current_state == "inactive":
                        api.do_transition_for(client, "activate")
                        self.log(
                            "Activate Client {}".format(row["Account_name"]),
                            action=True,
                        )
                    if client.Title != row["Account_name"]:
                        client = api.get_object(client)
                        self.log(
                            "Rename Client '{}' title to {}".format(
                                client.Title(), row["Account_name"]
                            ),
                            action=True,
                        )
                        client.setTitle(row["Account_name"])
                        client.reindexObject()
                        continue

            else:
                if row["Inactive"] == "1" or row["On_HOLD"] == "1":
                    self.log(
                        "Client {} doesn't exists but is marked as inactive/on_hold".format(
                            row["Account_name"]
                        )
                    )
                    continue
                client = api.create(
                    portal.clients,
                    "Client",
                    ClientID=row["Customer_Number"],
                    title=row["Account_name"],
                )
                self.log("Create Client {}".format(row["Account_name"]), action=True)
        return True

    def process_locations_rules(self, data):
        # portal = api.get_portal()
        # locations = api.search({"portal_type": "Client"})
        for row in data["rows"]:
            pass
        return True

    def process_systems_rules(self, data):
        return True

    def process_contacts_rules(self, data):
        return True
