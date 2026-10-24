from django.conf import settings
from django.db import models
from django.db.models import Q, F
class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey('posts.Post', on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=['user','post'], name='unique_like')]
class Follow(models.Model):
    source = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following')
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['source','target'], name='unique_follow'),models.CheckConstraint(condition=~Q(source=F('target')), name='no_self_follow')]
