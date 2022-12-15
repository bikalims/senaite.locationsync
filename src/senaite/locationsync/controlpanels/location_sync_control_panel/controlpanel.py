# -*- coding: utf-8 -*-
from plone.app.registry.browser.controlpanel import (
    ControlPanelFormWrapper,
    RegistryEditForm,
)
from plone.restapi.controlpanels import RegistryConfigletPanel
from plone.z3cform import layout
from zope import schema
from zope.component import adapter
from zope.interface import Interface

from senaite.locationsync import _
from senaite.locationsync.interfaces import ISenaiteLocationsyncLayer
from z3c.form import button

class ILocationSyncControlPanel(Interface):
    sync_base_folder = schema.TextLine(
        title=_(
            "Server base folder where the synconization files will be placed",
        ),
        required=True,
        readonly=False,
    )
    sync_email_user = schema.TextLine(
        title=_(
            "User of email account to which sync files are sent",
        ),
        required=True,
        readonly=False,
    )
    sync_email_password = schema.Password(
        title=_(
            "Password of email account to which sync files are sent",
        ),
        required=True,
        readonly=False,
    )
    sync_email_allowed_emails = schema.TextLine(
        title=_(
            "List of emails (comma separated) from which sync files can be sent",
        ),
        required=True,
        readonly=False,
    )
    sync_email_allowed_subjects = schema.TextLine(
        title=_(
            "Regular Expression to match sync email subjects",
        ),
        required=True,
        readonly=False,
    )
    sync_dest_emails = schema.TextLine(
        title=_(
            "List of additional emails (comma separeted) to which sync run results will be sent",
        ),
        required=True,
        readonly=False,
    )


class LocationSyncControlPanel(RegistryEditForm):
    schema = ILocationSyncControlPanel
    schema_prefix = "senaite.locationsync.location_sync_control_panel"
    label = _("Location Sync Settings")

    @button.buttonAndHandler(_('Cancel'), name='cancel')
    def handleCancel(self, action):
        super(LocationSyncControlPanel, self).handleCancel(self, action)

    @button.buttonAndHandler(_('Save'), name=None)
    def handleSave(self, action):
        super(LocationSyncControlPanel, self).handleSave(self, action)

    @button.buttonAndHandler(_('Run Sync Now'), name='run_sync')
    def handleRunSync(self, action):
        url = "{}/sync_locations_view".format(self.context.absolute_url())
        self.request.response.redirect(url)

    @button.buttonAndHandler(_('Log Files View'), name='log_files_view')
    def handleLogFilesView(self, action):
        url = "{}/log_file_view".format(self.context.absolute_url())
        self.request.response.redirect(url)

    @button.buttonAndHandler(_('Data Files View'), name='data_files_view')
    def handleLogFilesView(self, action):
        url = "{}/data_file_view".format(self.context.absolute_url())
        self.request.response.redirect(url)

LocationSyncControlPanelView = layout.wrap_form(
    LocationSyncControlPanel, ControlPanelFormWrapper
)


@adapter(Interface, ISenaiteLocationsyncLayer)
class LocationSyncControlPanelConfigletPanel(RegistryConfigletPanel):
    """Control Panel endpoint"""

    schema = ILocationSyncControlPanel
    configlet_id = "location_sync_control_panel-controlpanel"
    configlet_category_id = "Products"
    title = _("Location Sync Settings")
    group = ""
    schema_prefix = "senaite.locationsync.location_sync_control_panel"
