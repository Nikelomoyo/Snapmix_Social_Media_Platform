from django.contrib import admin
from .models import Mission, Membership, Invitation, Contribution, Reaction, Discussion

admin.site.register([Mission, Membership, Invitation, Contribution, Reaction, Discussion])
