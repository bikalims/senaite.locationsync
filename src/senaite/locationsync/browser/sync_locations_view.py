# -*- coding: utf-8 -*-

import csv
from DateTime import DateTime
import logging
import os
from plone.protect.interfaces import IDisableCSRFProtection
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
            self.log("Sync Base Folder {} does not exist".format(SYNC_BASE_FOLDER))
            success = False
        if not os.path.exists(SYNC_CURRENT_FOLDER):
            self.log(
                "Sync Current Folder {} does not exist".format(SYNC_CURRENT_FOLDER)
            )
            success = False
        if not os.path.exists(SYNC_ARCHIVE_FOLDER):
            self.log(
                "Sync Archive Folder {} does not exist".format(SYNC_ARCHIVE_FOLDER)
            )
            success = False
        if not os.path.exists(SYNC_ERROR_FOLDER):
            self.log("Sync Error Folder {} does not exist".format(SYNC_ERROR_FOLDER))
            success = False
        return success

    def log(self, message, level="info"):
        """Log to logging facility

        :param message: Log message
        :param level: Log level, e.g. debug, info, warning, error
        """
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
        self.process_file("Accounts", ACCOUNT_FILE_NAME)
        self.process_file("Locations", LOCATION_FILE_NAME)
        self.process_file("Systems", SYSTEM_FILE_NAME)
        self.process_file("Contacts", CONTACT_FILE_NAME)
        self.log("Sync process complete")

    def process_file(self, file_type, file_name):
        data = self.read_file_data(file_type, file_name)
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
            self.move_file(file_name, SYNC_ERROR_FOLDER)

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
            self.move_file(file_name, SYNC_ARCHIVE_FOLDER)
        else:
            self.move_file(file_name, SYNC_ERROR_FOLDER)

    def read_file_data(self, file_type, file_name):
        self.log("Read {} data file starting".format(file_type))
        file_path = "{}/{}".format(SYNC_CURRENT_FOLDER, file_name)
        if not os.path.exists(file_path):
            self.log("{} file not found".format(file_type))
            return {"headers": [], "rows": [], "errors": ["FileNotFound"]}

        headers = []
        rows = []
        errors = []
        with open(file_path) as csvfile:
            reader = csv.reader(csvfile, delimiter=",", quotechar='"')
            for i, row in enumerate(reader):
                if i == 0:
                    headers = row
                    self.log("File {} with {} headers".format(file_name, len(row)))
                    continue
                if len(headers) != len(row):
                    msg = "File {} incorrect number of columns {} in row {}: {}".format(
                        file_name, len(row), i, ", ".join(row)
                    )
                    errors.append(msg)
                    self.log(msg, level="error")
                    continue
                rows.append(row)
                # self.log("File {} row {}: {}".format(file_name, i, ", ".join(row)))
        self.log("Read {} data file complete".format(file_type))
        return {"headers": headers, "rows": rows, "errors": errors}

    def move_file(self, file_name, dest_folder):
        from_file_path = "{}/{}".format(SYNC_CURRENT_FOLDER, file_name)
        to_file_path = "{}/{}".format(dest_folder, file_name)
        os.rename(from_file_path, to_file_path)

    def process_account_rules(self, data):
        return True

    def process_locations_rules(self, data):
        return True

    def process_systems_rules(self, data):
        return True

    def process_contacts_rules(self, data):
        return True
