from django.conf import settings
from django.db import models
from django.utils import timezone
from .storage import MissionStorage


class Mission(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Open to everyone'
        INVITE = 'invite', 'Invite only'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='missions_created')
    title = models.CharField(max_length=100)
    prompt = models.TextField(max_length=1200)
    cover = models.ImageField(upload_to='covers/', storage=MissionStorage(), blank=True)
    visibility = models.CharField(max_length=8, choices=Visibility.choices, default=Visibility.PUBLIC)
    ends_at = models.DateTimeField(db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    @property
    def is_closed(self):
        return self.closed_at is not None or self.ends_at <= timezone.now()

    @property
    def deadline(self):
        return self.closed_at or self.ends_at


class Membership(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mission_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['mission', 'user'], name='unique_mission_member')]


class Invitation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name='invitations')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mission_invites_sent')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mission_invites')
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['mission', 'recipient'], name='unique_mission_invitation')]


class Contribution(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name='contributions')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mission_contributions')
    text = models.TextField(max_length=1200, blank=True)
    image = models.ImageField(upload_to='contributions/', storage=MissionStorage(), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [models.UniqueConstraint(fields=['mission', 'author'], name='one_contribution_per_person')]


class Reaction(models.Model):
    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['contribution', 'user'], name='unique_mission_reaction')]


class Discussion(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name='discussion')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
