import os
from io import BytesIO
from PIL import Image, ImageDraw
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from posts.models import Post, Comment
from social.models import Follow, Like
from chat.models import Conversation, Message
from notifications.models import Notification
class Command(BaseCommand):
    help='Create repeatable demo content. Set DEMO_PASSWORD or pass --password.'
    def add_arguments(self,parser): parser.add_argument('--password')
    def handle(self,*args,**options):
        password=options['password'] or os.getenv('DEMO_PASSWORD')
        if not password: raise CommandError('Set DEMO_PASSWORD or pass --password (local demo only).')
        names=[('alex','Alex Morgan','Collecting moments, not things. ☀','Cape Town'),('zola','Zola Dlamini','Design, music & a little bit of everything.','Johannesburg'),('kai','Kai Williams','Taking the scenic route. Always.','Durban'),('mia','Mia Patel','Coffee first. Big ideas second.','Cape Town'),('leo','Leo Jacobs','Making things that make people smile.','Pretoria')]
        users=[]
        for username,name,bio,location in names:
            u,created=User.objects.get_or_create(username=username)
            if created: u.set_password(password);u.save()
            p=u.profile;p.display_name=name;p.bio=bio;p.location=location;p.save();users.append(u)
        for u in users[1:3]: Follow.objects.get_or_create(source=users[0],target=u)
        texts=['A reminder to take the long way home sometimes. You never know what you’ll find. 🌅','Made a tiny playlist for big main-character energy. What’s the one song you have on repeat? 🎧','Offline for a bit. Out here finding the good stuff. 🌿','Today’s agenda: good coffee, better conversations, and absolutely no rushing. ☕','Your weird little idea might be somebody’s favourite thing. Make it anyway. ✨']
        for index,u in enumerate(users):
            post,created=Post.objects.get_or_create(author=u,text=texts[index])
            if created and index in [0,2]:
                im=Image.new('RGB',(1000,620),'#d8b48d');d=ImageDraw.Draw(im)
                if index==0:
                    for y in range(620):
                        t=y/620;d.line((0,y,1000,y),fill=(int(234-110*t),int(186-45*t),int(130-34*t)))
                    d.ellipse((670,80,800,210),fill='#fff0b6');d.polygon([(0,440),(230,260),(490,430),(720,340),(1000,480),(1000,620),(0,620)],fill='#596359');d.polygon([(0,520),(350,420),(650,510),(1000,400),(1000,620),(0,620)],fill='#303e36')
                else:
                    im.paste('#c3d1b0',(0,0,1000,620));d=ImageDraw.Draw(im)
                    for x,y,r,c in [(100,100,210,'#4e6c49'),(450,0,260,'#759466'),(820,180,330,'#3b5e45'),(300,500,260,'#244c38')]:d.ellipse((x-r,y-r,x+r,y+r),fill=c)
                    d.polygon([(430,620),(580,220),(640,220),(690,620)],fill='#d6c7a5')
                buf=BytesIO();im.save(buf,format='JPEG');post.image.save(f'demo-{index}.jpg',ContentFile(buf.getvalue()))
            for admirer in users:
                if admirer!=u: Like.objects.get_or_create(user=admirer,post=post)
            Comment.objects.get_or_create(author=users[(index+1)%len(users)],post=post,text='This is exactly the energy I needed today ✨')
        a,b=sorted([users[0].pk,users[1].pk]);room,_=Conversation.objects.get_or_create(a_id=a,b_id=b)
        Message.objects.get_or_create(conversation=room,sender=users[1],text='Hey Alex! Welcome to the mix 👋')
        Notification.objects.get_or_create(recipient=users[0],actor=users[1],verb='started following you')
        from pathlib import Path
        from django.conf import settings
        from django.core.management import call_command
        if (Path(settings.BASE_DIR)/'static'/'demo'/'coast.jpg').exists():
            call_command('enrich_demo')
        call_command('seed_missions')
        self.stdout.write(self.style.SUCCESS('Demo ready. Log in as alex, zola, kai, mia or leo with the supplied password. Existing passwords are unchanged.'))
