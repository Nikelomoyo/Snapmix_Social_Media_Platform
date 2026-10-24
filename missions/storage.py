import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class MissionStorage(FileSystemStorage):
    """Keep mission files outside public /media; views check access per request."""
    @property
    def base_location(self):
        return settings.MISSION_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError('Mission files must use the permission-checked media view.')
