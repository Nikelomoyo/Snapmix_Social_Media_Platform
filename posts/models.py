from django.conf import settings
from django.db import models
from accounts.topics import TOPIC_CHOICES, infer_topic
class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    text = models.TextField(max_length=2000, blank=True)
    image = models.ImageField(upload_to='posts/', blank=True)
    topic = models.CharField(max_length=24, choices=TOPIC_CHOICES, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta: ordering = ['-created_at','-pk']
    def save(self,*args,**kwargs):
        if not self.topic:
            self.topic=infer_topic(self.text)
        super().save(*args,**kwargs)
class Comment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['created_at','pk']
