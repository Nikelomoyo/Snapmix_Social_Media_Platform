from django.conf import settings
from django.db import models
class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=60, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    bio = models.CharField(max_length=280, blank=True)
    location = models.CharField(max_length=80, blank=True)
    interests = models.JSONField(default=list, blank=True)
    interests_set = models.BooleanField(default=False)
    learn_from_activity = models.BooleanField(default=True)
    @property
    def name(self):
        return self.display_name or self.user.username
