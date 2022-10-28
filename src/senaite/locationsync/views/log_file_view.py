# -*- coding: utf-8 -*-

# from senaite.locationsync import _
import glob
import logging
import os
from Products.Five.browser import BrowserView
from senaite import api
import StringIO
from zope.interface import Interface

logger = logging.getLogger("locations_sync")


class ILogFileView(Interface):
    """Marker Interface for ILogFileView"""


class LogFileView(BrowserView):
    def __call__(self):
        # Implement your own actions:
        return self.index()

    def get_data(self):
        base_folder = api.get_registry_record(
            "senaite.locationsync.location_sync_control_panel.sync_base_folder"
        )
        if base_folder is None:
            logger.info(
                'get_log_file: control panel field "senaite.locationsync.location_sync_control_panel.sync_base_folder" is not set'
            )
            return
        files = []
        if base_folder:
            path = "{}/logs".format(base_folder)
            if os.path.exists(path):
                listing = glob.glob(path + "/*")
                listing.sort(key=lambda x: os.path.getmtime(x))
                listing = [f.split("/")[-1] for f in listing]
                for name in listing:
                    # TODO url hardcoded!!!
                    file_dict = {
                        "name": name,
                        "url": "/@@get_log_file?name={}".format(name),
                    }
                    if "localhost" in self.context.absolute_url():
                        file_dict["url"] = "/senaite3/@@get_log_file?name={}".format(
                            name
                        )

                    files.append(file_dict)
        logger.info("get_data: return {}".format(files))
        return {"files": files}

    def get_log_file(self):
        form = self.request.form
        name = form.get("name")
        if name is None:
            logger.info("get_log_file: name param is requried")
            return
        base_folder = api.get_registry_record(
            "senaite.locationsync.location_sync_control_panel.sync_base_folder"
        )
        if base_folder is None:
            logger.info(
                'get_log_file: control panel field "senaite.locationsync.location_sync_control_panel.sync_base_folder" is not set'
            )
            return

        path = "{}/logs/{}".format(base_folder, name)
        if not os.path.exists(path):
            logger.info("get_log_file: file '{}' does not exist".format(path))
            return
        # get file and return it
        logger.info("return file '{}'".format(path))
        self.request.response.setHeader("Content-Type", "text/csv")
        self.request.response.setHeader(
            "Content-Disposition", 'attachment; filename="{}"'.format(name)
        )
        with open(path) as f:
            contents = f.read()
        out = StringIO.StringIO(contents)
        return out.getvalue()
