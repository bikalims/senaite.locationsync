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


class ILocationSyncControlPanel(Interface):
    sync_base_folder = schema.TextLine(
        title=_(
            "Server base folder where the synconization files will be placed",
        ),
        required=True,
        readonly=False,
    )


class LocationSyncControlPanel(RegistryEditForm):
    schema = ILocationSyncControlPanel
    schema_prefix = "senaite.locationsync.location_sync_control_panel"
    label = _("Location Sync Settings")


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
