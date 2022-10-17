# -*- coding: utf-8 -*-
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import (
    FunctionalTesting,
    IntegrationTesting,
    PloneSandboxLayer,
    applyProfile,
)
from plone.testing import z2

import senaite.locationsync


class SenaiteLocationsyncLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.restapi

        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=senaite.locationsync)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "senaite.locationsync:default")


SENAITE_LOCATIONSYNC_FIXTURE = SenaiteLocationsyncLayer()


SENAITE_LOCATIONSYNC_INTEGRATION_TESTING = IntegrationTesting(
    bases=(SENAITE_LOCATIONSYNC_FIXTURE,),
    name="SenaiteLocationsyncLayer:IntegrationTesting",
)


SENAITE_LOCATIONSYNC_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(SENAITE_LOCATIONSYNC_FIXTURE,),
    name="SenaiteLocationsyncLayer:FunctionalTesting",
)


SENAITE_LOCATIONSYNC_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        SENAITE_LOCATIONSYNC_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name="SenaiteLocationsyncLayer:AcceptanceTesting",
)
