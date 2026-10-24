from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from missions.models import Mission, Membership, Invitation, Contribution, Reaction, Discussion
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Add repeatable Mix Missions examples using the existing fictional demo accounts.'

    def handle(self, *args, **options):
        people = {u.username: u for u in User.objects.filter(username__in=['alex', 'zola', 'kai', 'mia', 'leo'])}
        if len(people) < 5:
            raise CommandError('Run seed_demo --password YOUR_LOCAL_DEMO_PASSWORD first.')
        photos = Path(settings.BASE_DIR) / 'static' / 'demo'
        now = timezone.now()
        examples = [
            ('alex', 'Your city, one colour', 'Find a little green in your everyday city. A street corner, your favourite plant, a quiet escape. One perspective each — let’s make a new map together.', 'forest', 'public', False,
             [('alex','forest','A pocket of calm between the busy streets.'),('kai','coastline','Taking the scenic route to find a different kind of green.'),('zola','coffee','A little green, a good coffee, a slower morning.')]),
            ('mia', 'One good thing today', 'Share one small moment that made today a little better. No perfect photos needed. Just the real, ordinary good stuff.', 'coffee', 'public', False,
             [('mia','coffee','A table by the window. Time to think.'),('leo',None,'A friend remembered a tiny thing I told them last week. That was the good thing.'),('alex','sunset','Stayed for the last light instead of rushing home.')]),
            ('kai', 'Our dream weekend', 'One person, one idea. Bring a place, a plan or a little adventure, and build a weekend we would all love.', 'coast', 'public', True,
             [('kai','beach','Start with a walk along the coast. No alarm clock.'),('zola','city','Get lost in a new neighbourhood, find a tiny gallery.'),('mia','coffee','Finish around a table, with a coffee and everyone’s stories.')]),
            ('zola', 'The little things club', 'A small collection for our circle. Show us one detail you noticed that everyone else might have walked past.', 'architecture', 'invite', False,
             [('zola','architecture','The pattern of light changes every time I walk past.')]),
        ]
        for owner_name, title, prompt, cover, visibility, finished, contributions in examples:
            mission, created = Mission.objects.get_or_create(owner=people[owner_name], title=title, defaults={
                'prompt': prompt, 'visibility': visibility,
                'ends_at': now-timedelta(days=1) if finished else now+timedelta(days=3),
            })
            if created and (photos/f'{cover}.jpg').exists():
                mission.cover.save(f'mission-{cover}.jpg', ContentFile((photos/f'{cover}.jpg').read_bytes()))
            if created and finished:
                Mission.objects.filter(pk=mission.pk).update(created_at=now-timedelta(days=3))
            Membership.objects.get_or_create(mission=mission,user=people[owner_name])
            for name, photo, text in contributions:
                Membership.objects.get_or_create(mission=mission,user=people[name])
                entry, entry_created = Contribution.objects.get_or_create(mission=mission,author=people[name],defaults={'text':text})
                if entry_created and photo and (photos/f'{photo}.jpg').exists():
                    entry.image.save(f'perspective-{photo}.jpg',ContentFile((photos/f'{photo}.jpg').read_bytes()))
                if entry_created and finished:
                    Contribution.objects.filter(pk=entry.pk).update(created_at=now-timedelta(days=2),updated_at=now-timedelta(days=2))
                Reaction.objects.get_or_create(contribution=entry,user=people[owner_name])
            if created:
                discussion=Discussion.objects.create(mission=mission,author=people[owner_name],text='Different eyes, one shared story. I love seeing everyone’s take on this.')
                if finished:
                    Discussion.objects.filter(pk=discussion.pk).update(created_at=now-timedelta(days=2))
            if visibility == 'invite':
                invitation, invited = Invitation.objects.get_or_create(mission=mission,recipient=people['alex'],defaults={'sender':people[owner_name]})
                if invited:
                    Notification.objects.create(mission=mission,recipient=people['alex'],actor=people[owner_name],verb='invited you to a mission')
        self.stdout.write(self.style.SUCCESS('Mix Missions ready: open challenges, a finished collection and an invite-only example. Existing missions were preserved.'))
