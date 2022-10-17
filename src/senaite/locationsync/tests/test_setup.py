# -*- coding: utf-8 -*-
"""Setup tests for this package."""
import unittest

from plone import api
from plone.app.testing import TEST_USER_ID, setRoles

from senaite.locationsync.testing import (  # noqa: E501
    SENAITE_LOCATIONSYNC_INTEGRATION_TESTING,
)

try:
    from Products.CMFPlone.utils import get_installer
except ImportError:
    get_installer = None


class TestSetup(unittest.TestCase):
    """Test that senaite.locationsync is properly installed."""

    layer = SENAITE_LOCATIONSYNC_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        if get_installer:
            self.installer = get_installer(self.portal, self.layer["request"])
        else:
            self.installer = api.portal.get_tool("portal_quickinstaller")

    def test_product_installed(self):
        """Test if senaite.locationsync is installed."""
        self.assertTrue(self.installer.is_product_installed("senaite.locationsync"))

    def test_browserlayer(self):
        """Test that ISenaiteLocationsyncLayer is registered."""
        from plone.browserlayer import utils

        from senaite.locationsync.interfaces import ISenaiteLocationsyncLayer

        self.assertIn(ISenaiteLocationsyncLayer, utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = SENAITE_LOCATIONSYNC_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        if get_installer:
            self.installer = get_installer(self.portal, self.layer["request"])
        else:
            self.installer = api.portal.get_tool("portal_quickinstaller")
        roles_before = api.user.get_roles(TEST_USER_ID)
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.installer.uninstall_product("senaite.locationsync")
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if senaite.locationsync is cleanly uninstalled."""
        self.assertFalse(self.installer.is_product_installed("senaite.locationsync"))

    def test_browserlayer_removed(self):
        """Test that ISenaiteLocationsyncLayer is removed."""
        from plone.browserlayer import utils

        from senaite.locationsync.interfaces import ISenaiteLocationsyncLayer

        self.assertNotIn(ISenaiteLocationsyncLayer, utils.registered_layers())
