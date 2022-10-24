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

        # TODO this should only be moved after all files are processed
        # Any errors shold move all to Error folder
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

        # Prep clients
        clients = api.search({"portal_type": "Client"})
        client_ids = [c["getClientID"] for c in clients]
        for i, row in enumerate(data["rows"]):
            if len(row.get("Customer_Number", "")) == 0:
                self.log(
                    "Row {} of Account file has no Customer_Number value".format(i),
                    level="error",
                )
                continue
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
                    else:
                        api.do_transition_for(client, "deactivate")
                        self.log(
                            "Deactivate Client {}".format(row["Account_name"]),
                            action=True,
                        )
                else:
                    # marked in file as active
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
            else:
                # Client not in DB
                client = api.create(
                    portal.clients,
                    "Client",
                    ClientID=row["Customer_Number"],
                    title=row["Account_name"],
                )
                self.log("Created Client {}".format(row["Account_name"]), action=True)
                if row["Inactive"] == "1" or row["On_HOLD"] == "1":
                    api.do_transition_for(client, "deactivate")
                    self.log(
                        "Deactivate newly created client {}".format(
                            row["Account_name"]
                        ),
                        action=True,
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
            lab_contact_names.append(contact.getFullname())

        # Prep clients
        clients = api.search({"portal_type": "Client"})
        client_ids = [c["getClientID"] for c in clients]
        for i, row in enumerate(data["rows"]):
            # field validation - required fields
            if len(row.get("Customer_Number", "")) == 0:
                self.log(
                    "Row {} of Locations file has no Customer_Number value".format(i),
                    level="error",
                )
                continue
            if len(row.get("Locations_id", "")) == 0:
                self.log(
                    "Row {} of Locations file has no Locations_id value".format(i),
                    level="error",
                )
                continue
            # field validation - client must exist
            if row["Customer_Number"] not in client_ids:
                self.log(
                    "Client ID {} on row {} of the locations file was not found in DB".format(
                        row["Customer_Number"], i
                    ),
                    level="error",
                )
                # TODO notify lab admin
                continue
            client = [c for c in clients if row["Customer_Number"] == c["getClientID"]][
                0
            ]
            self.log("Found Client {}".format(row["Customer_Number"]))
            locations = api.search(
                {
                    "portal_type": "SamplePointLocation",
                    "query": {"path": client.getPath()},
                }
            )
            # TODO add location ID to catalog and use it here
            locations = [api.get_object(l) for l in locations]
            location_ids = [l.system_location_id for l in locations]
            if row["Locations_id"] in location_ids:
                # Location exists
                location = [
                    l
                    for l in locations
                    if row["Locations_id"] == l.get_system_location_id()
                ][0]
                # If row['HOLD'] or row['Cancel_Box'], see code below
                # If row['account_manager1'], see code below
                # For address field in row, see code below
                self.log("Found location {}".format(row["Locations_id"]))
            else:
                # Location does NOT exist
                client = api.get_object(client)
                title = row["location_name"].replace("/", "")
                location = api.create(
                    client,
                    "SamplePointLocation",
                    title=title,
                )
                location.set_system_location_id(row["Locations_id"])
                self.log(
                    "Created location {} in Client {}".format(
                        location.Title(), client.Title()
                    ),
                    action=True,
                )
            # Rules for if location existed or has just been created
            if row["HOLD"] == "1" or row["Cancel_Box"] == "1":
                # deactivate location and children
                current_state = api.get_workflow_status_of(location)
                if current_state == "active":
                    api.do_transition_for(location, "deactivate")
                    self.log(
                        "Location {} in Client {} has been deactivated".format(
                            row["location_name"], client.Title()
                        ),
                        action=True,
                    )
                for system in location.values():
                    current_state = api.get_workflow_status_of(system)
                    if current_state == "active":
                        api.do_transition_for(system, "deactivate")
                        self.log(
                            "System {} in Location {} in Client {} has been deactivated".format(
                                system.Title(), row["location_name"], client.Title()
                            ),
                            action=True,
                        )
            if row["account_manager1"]:
                if row["account_manager1"] in lab_contact_names:
                    contact = [
                        c
                        for c in lab_contacts
                        if row["account_manager1"] == c.getFullname()
                    ][0]
                    self.log(
                        "Found lab contact {} for Location {}".format(
                            contact.getFullname(), location.Title()
                        ),
                    )
                else:
                    contact = api.create(
                        lab_contacts_folder,
                        "LabContact",
                        Firstname=" ".join(row["account_manager1"].split(" ")[:-1]),
                        Surname=row["account_manager1"].split(" ")[-1],
                    )
                    lab_contacts.append(contact)
                    lab_contact_names.append(contact.getFullname())
                    self.log(
                        "Created a Lab Contact {} for location {} and client {}".format(
                            contact.getFullname(), location.Title(), client.Title()
                        ),
                        action=True,
                    )
                    # TODO Notify lab admin that new lab contact created with no email
                contacts = location.get_account_managers()
                if (
                    len(
                        [
                            c
                            for c in contacts
                            if c.getFullname() == contact.getFullname()
                        ]
                    )
                    == 0
                ):
                    # Added to location acccount managers if not already in there
                    contacts.append(contact)
                    location.set_account_managers(contacts)
                    self.log(
                        "Addd Lab Contact {} to location {} and client {}".format(
                            contact.getFullname(), location.Title(), client.Title()
                        ),
                        action=True,
                    )
                # Get address from row and update location, new or old
                address = self._get_address_field(row)
                location.address = [address]

        return True

    def process_systems_rules(self, data):
        locations = api.search({"portal_type": "SamplePointLocation"})
        locations = [api.get_object(l) for l in locations]
        location_ids = [l.get_system_location_id() for l in locations]
        for i, row in enumerate(data["rows"]):
            if len(row.get("SystemID", "")) == 0:
                self.log(
                    "System on row {} with name {} in location {} has no SystemID field".format(
                        i,
                        row.get("system_name", "missing"),
                        row.get("Location_id", "missing"),
                    ),
                    level="error",
                )
                continue
            if row["Location_id"] not in location_ids:
                msg = "Location {} on row {} in systems file not found in DB".format(
                    row["Location_id"], i
                )
                self.log(msg, level="error")
                # TODO Notify lab admin location not found
                continue
            location = [
                l for l in locations if row["Location_id"] == l.get_system_location_id()
            ][0]
            self.log("Found Location {}".format(row["Location_id"]))
            # TODO is location id in catalog?
            systems = api.search(
                {
                    "portal_type": "SamplePoint",
                    "query": {"path": "/".join(location.getPhysicalPath())},
                }
            )
            systems = [api.get_object(s) for s in systems]
            system = None
            for sys in systems:
                if hasattr(sys, "SystemId"):
                    if sys.SystemId == row["SystemID"]:
                        system = sys
                        break
            if system is not None:
                self.log(
                    "Found System {} with ID {} in Location {}".format(
                        system.Title(), row["SystemID"], location.Title()
                    )
                )
            else:
                # Create new system
                if row["Inactive_Retired_Flag"] == "1":
                    self.log(
                        "System {} in location {} doesn't exists but is marked as Inactive_Retired_Flag".format(
                            row["system_name"], location.Title
                        )
                    )
                    continue
                location = api.get_object(location)
                system = api.create(
                    location,
                    "SamplePoint",
                    title=row["system_name"],
                )
                system.SystemId = row["SystemID"]
                client_title = location.aq_parent.Title()
                self.log(
                    "Created system {} in location {} in client {}".format(
                        system.Title(), location.Title(), client_title
                    ),
                    action=True,
                )
            system.EquipmentID = row["Equipment_ID"]
            system.EquipmentType = row["system"]
            system.EquipmentDescription = row["Equipment_Description2"]

        return True

    def process_contacts_rules(self, data):
        locations = api.search({"portal_type": "SamplePointLocation"})
        locations = [api.get_object(l) for l in locations]
        location_ids = [l.get_system_location_id() for l in locations]
        for i, row in enumerate(data["rows"]):
            if len(row.get("contactID", "")) == 0:
                self.log(
                    "Contact on row {} in location {} has no contactID field".format(
                        i, row.get("Locations_id", "missing")
                    ),
                    level="error",
                )
                continue
            if len(row.get("Locations_id", "")) == 0:
                self.log(
                    "Contact on row {} with contactID {} has no Locations_id field".format(
                        i, row.get("contactID", "missing")
                    ),
                    level="error",
                )
                continue
            if row["Locations_id"] not in location_ids:
                msg = "Location {} on row {} in contacts file not found in DB".format(
                    row["Locations_id"], i
                )
                self.log(msg, level="error")
                continue

            self.log("Found Location {}".format(row["Locations_id"]))
            location = [
                l
                for l in locations
                if row["Locations_id"] == l.get_system_location_id()
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
            contact_ids = [c.ContactId for c in contacts]
            if row["contactID"] in contact_ids:
                self.log(
                    "Found contact {} in location {}".format(
                        row["contactID"], location.Title()
                    )
                )
                # TODO more processing here
                continue
            else:
                contact = api.create(
                    client,
                    "Contact",
                    Surname=row.get("WS_Contact_Name", "Missing"),
                )
                contact.ContactId = row["contactID"]
                self.log(
                    "Created contact {} for location {} in client {}".format(
                        contact.ContactId, location.Title(), client.Title()
                    ),
                    action=True,
                )
            # TODO Ensure email is correct
            contact.setEmailAddress(row["email"])
            self.log(
                "Added contact {} to location {} in client {}".format(
                    contact.Title(), location.Title(), client.Title()
                ),
                action=True,
            )
        return True

    def _get_address_field(self, row):
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
            raise RuntimeError("Unknown state abbreviation {}".format(state))
        address = {
            u"address": row.get("street", ""),
            u"city": row.get("city", ""),
            u"country": u"Australia",
            u"subdivision1": state_vocab[state],
            u"subdivision2": u"",
            u"type": u"physical",
            u"zip": row.get("postcode", ""),
        }
        return address
