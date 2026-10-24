from django.conf import settings
from django.db import models
from django.db.models import Q, F
class Conversation(models.Model):
    a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations_a')
    b = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations_b')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['a','b'], name='unique_pair'),models.CheckConstraint(condition=Q(a__lt=F('b')), name='ordered_pair')]
    def includes(self, user): return user.pk in (self.a_id, self.b_id)
class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.CharField(max_length=2000)
    client_id = models.UUIDField(null=True, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['conversation', 'sender', 'client_id'], name='unique_message_retry')]
