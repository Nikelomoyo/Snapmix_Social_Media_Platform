"""Add photographed demo content without replacing user-created content."""
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from chat.models import Conversation, Message
from notifications.models import Notification
from posts.models import Post, Comment
from social.models import Follow, Like

class Command(BaseCommand):
    help = 'Populate only the five fictional SnapMix demo accounts with stock photography.'

    def handle(self, *args, **options):
        directory=Path(settings.BASE_DIR)/'static'/'demo'
        photos=['coast','forest','city','coffee','architecture','sunset','beach','coastline']
        if any(not (directory/f'{name}.jpg').exists() for name in photos):
            raise CommandError('Download demo photography first: python scripts/fetch_demo_photos.py')
        users=list(User.objects.filter(username__in=['alex','zola','kai','mia','leo']).select_related('profile').order_by('username'))
        if len(users)!=5:
            raise CommandError('Run seed_demo with a local demo password first.')
        by_name={u.username:u for u in users}
        original={
            'alex':('A reminder to take the long way home sometimes. You never know what you’ll find. 🌅','sunset'),
            'zola':('Made a tiny playlist for big main-character energy. What’s the one song you have on repeat? 🎧','city'),
            'kai':('Offline for a bit. Out here finding the good stuff. 🌿','forest'),
            'mia':('Today’s agenda: good coffee, better conversations, and absolutely no rushing. ☕','coffee'),
            'leo':('Your weird little idea might be somebody’s favourite thing. Make it anyway. ✨','architecture'),
        }
        def attach(post, name):
            post.image.save(f'snapmix-{post.author.username}-{name}.jpg',ContentFile((directory/f'{name}.jpg').read_bytes()))
        for username,(text,photo) in original.items():
            post=Post.objects.filter(author=by_name[username],text=text).first()
            if post and (not post.image or Path(post.image.name).name.startswith('demo-') or (username=='alex' and Path(post.image.name).name=='snapmix-alex-coast.jpg')):
                attach(post,photo)
        for user in users:
            portrait=directory/f'avatar-{user.username}.jpg'
            if not user.profile.avatar and portrait.exists():
                user.profile.avatar.save(f'demo-{user.username}.jpg',ContentFile(portrait.read_bytes()))
        collections={
            'alex':[('coast','A slow evening, an open horizon, and nowhere else to be.'),('coffee','Small rituals that make an ordinary day feel good.'),('coastline','Keeping a little space for the scenic route.'),('city','Looking up changes the whole walk.')],
            'kai':[('forest','Trading the noise for a trail through the trees.'),('coastline','A little ocean air goes a long way.'),('beach','The best part of the day costs absolutely nothing.'),('architecture','Collecting lines, light and new perspectives.')],
            'zola':[('city','Textures, little details, and the rhythm of a city.'),('architecture','Old stories, new angles. A few frames from the camera roll.'),('coffee','A coffee break and a fresh page. Starting somewhere.'),('sunset','A good reminder to put the phone down after this photo.')],
            'mia':[('coffee','A table by the window is always the right choice.'),('sunset','Ending the day on a softer note.'),('beach','No itinerary. Just this view for a while.'),('forest','Making time for places that help me slow down.')],
            'leo':[('architecture','Finding inspiration in the places we walk past.'),('city','A new perspective is usually one street away.'),('coast','Some colours are better than any mood board.'),('coastline','Saving this one for a day that needs a little more space.')],
        }
        now=timezone.now()
        for round_index in range(4):
            for person_index,username in enumerate(['alex','kai','zola','mia','leo']):
                photo,text=collections[username][round_index]
                user=by_name[username]
                post,created=Post.objects.get_or_create(author=user,text=text)
                if created:
                    attach(post,photo)
                    Post.objects.filter(pk=post.pk).update(created_at=now-timedelta(hours=round_index*18+person_index*2+1))
                for liker in users:
                    if liker!=user:
                        Like.objects.get_or_create(user=liker,post=post)
                commenter=users[(users.index(user)+1)%len(users)]
                Comment.objects.get_or_create(post=post,author=commenter,text=['This light is everything.','Adding this to my weekend inspiration.','A whole mood. Love this frame.','Could spend a whole afternoon here.'][round_index])
        for index,user in enumerate(users):
            for offset in [1,2]:
                target=users[(index+offset)%len(users)]
                Follow.objects.get_or_create(source=user,target=target)
            recent=user.posts.first()
            actor=users[(index+1)%len(users)]
            Notification.objects.get_or_create(recipient=user,actor=actor,verb='liked your post',post=recent)
            Notification.objects.get_or_create(recipient=user,actor=actor,verb='commented on your post',post=recent)
        alex=by_name['alex']
        for name,text in [('kai','Found a new trail for the weekend. Are you in?'),('mia','Coffee sometime this week? I found a lovely little spot.')]:
            other=by_name[name];a,b=sorted([alex.pk,other.pk])
            room,_=Conversation.objects.get_or_create(a_id=a,b_id=b)
            Message.objects.get_or_create(conversation=room,sender=other,text=text)
            Message.objects.get_or_create(conversation=room,sender=alex,text='That sounds good! Send me the details.')
        self.stdout.write(self.style.SUCCESS('Demo photography, collections and conversations ready. User-created posts and profile images were preserved.'))
