from django.conf import settings
from django.db import models
class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    verb = models.CharField(max_length=40)
    post = models.ForeignKey('posts.Post', on_delete=models.CASCADE, null=True, blank=True)
    mission = models.ForeignKey('missions.Mission', on_delete=models.CASCADE, null=True, blank=True)
    read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at','-pk']
