# -*- coding: utf-8 -*-

# from senaite.locationsync import _
from Products.Five.browser import BrowserView
from zope.interface import Interface

# from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile


class ILogFileView(Interface):
    """Marker Interface for ILogFileView"""


class LogFileView(BrowserView):
    # If you want to define a template here, please remove the template from
    # the configure.zcml registration of this view.
    # template = ViewPageTemplateFile('log_file_view.pt')

    def __call__(self):
        # Implement your own actions:
        return self.index()
