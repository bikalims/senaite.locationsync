# -*- coding: utf-8 -*-
import unittest

from plone import api
from plone.app.testing import TEST_USER_ID, setRoles
from zope.component import getMultiAdapter
from zope.interface.interfaces import ComponentLookupError

from senaite.locationsync.testing import (
    SENAITE_LOCATIONSYNC_FUNCTIONAL_TESTING,
    SENAITE_LOCATIONSYNC_INTEGRATION_TESTING,
)


class ViewsIntegrationTest(unittest.TestCase):

    layer = SENAITE_LOCATIONSYNC_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        api.content.create(self.portal, "Folder", "other-folder")
        api.content.create(self.portal, "Document", "front-page")

    def test_sync_locations_view_is_registered(self):
        view = getMultiAdapter(
            (self.portal["other-folder"], self.portal.REQUEST),
            name="sync_locations_view",
        )
        self.assertTrue(view.__name__ == "sync_locations_view")
        # self.assertTrue(
        #     'Sample View' in view(),
        #     'Sample View is not found in sync_locations_view'
        # )

    def test_sync_locations_view_not_matching_interface(self):
        with self.assertRaises(ComponentLookupError):
            getMultiAdapter(
                (self.portal["front-page"], self.portal.REQUEST),
                name="sync_locations_view",
            )


class ViewsFunctionalTest(unittest.TestCase):

    layer = SENAITE_LOCATIONSYNC_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
