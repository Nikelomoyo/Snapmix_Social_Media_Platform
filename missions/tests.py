from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from notifications.models import Notification
from .models import Mission, Membership, Invitation, Contribution, Reaction, Discussion


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner=User.objects.create_user('host',password='Test-pass-123!')
        self.friend=User.objects.create_user('friend',password='Test-pass-123!')
        self.other=User.objects.create_user('other',password='Test-pass-123!')
        self.mission=Mission.objects.create(owner=self.owner,title='Our green city',prompt='Find something green.',ends_at=timezone.now()+timedelta(days=2))
        Membership.objects.create(mission=self.mission,user=self.owner)
        self.client.force_login(self.friend)
        self.temporary=TemporaryDirectory()
        self.storage=override_settings(MISSION_MEDIA_ROOT=self.temporary.name)
        self.storage.enable()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.storage.disable)

    def url(self, action, **kwargs):
        return reverse('missions:'+action,kwargs={'pk':self.mission.pk,**kwargs})

    def image(self):
        data=BytesIO();Image.new('RGB',(20,20),'green').save(data,'PNG')
        return SimpleUploadedFile('green.png',data.getvalue(),content_type='image/png')

    def join(self):
        return self.client.post(self.url('join'))

    def test_create_and_form_validation(self):
        form={'title':'Our shared morning','prompt':'Find one good moment.','visibility':'public','ends_at':timezone.localtime(timezone.now()+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')}
        self.assertEqual(self.client.post(reverse('missions:create'),form).status_code,302)
        created=Mission.objects.get(title=form['title'])
        self.assertEqual(created.owner,self.friend)
        self.assertTrue(created.memberships.filter(user=self.friend).exists())
        form['ends_at']='2001-01-01T10:00'
        self.assertContains(self.client.post(reverse('missions:create'),form),'Choose a closing time')
        form['ends_at']=timezone.localtime(timezone.now()+timedelta(days=40)).strftime('%Y-%m-%dT%H:%M')
        self.assertEqual(self.client.post(reverse('missions:create'),form).status_code,200)
        self.assertEqual(Mission.objects.count(),2)
        self.assertContains(self.client.get(reverse('missions:create')+'?idea=colour'),'Your city, one colour')

    def test_join_is_idempotent_and_permissions_apply_to_writes(self):
        self.assertEqual(self.client.get(self.url('join')).status_code,405)
        self.assertEqual(self.client.post(self.url('invite'),{'username':'other'}).status_code,404)
        self.assertEqual(self.client.post(self.url('contribute'),{'text':'No membership'}).status_code,404)
        self.assertEqual(self.join().status_code,302);self.join()
        self.assertEqual(self.mission.memberships.count(),2)
        self.assertEqual(Notification.objects.filter(mission=self.mission,verb='joined your mission').count(),1)
        self.assertEqual(self.client.post(self.url('close')).status_code,404)

    def test_invite_only_board_detail_updates_and_join_are_private(self):
        self.mission.visibility='invite';self.mission.save()
        for action in ['detail','updates','contribute']:
            self.assertEqual(self.client.get(self.url(action)).status_code,404)
        self.assertEqual(self.join().status_code,404)
        self.assertNotContains(self.client.get(reverse('missions:board')),self.mission.title)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('invite'),{'username':'friend'}).status_code,302)
        self.client.force_login(self.friend)
        self.assertContains(self.client.get(reverse('missions:board')+'?tab=invites'),self.mission.title)
        self.assertContains(self.client.get(self.url('detail')),'YOU’RE INVITED')
        self.assertEqual(self.client.post(self.url('respond'),{'action':'accept'}).status_code,302)
        self.assertTrue(self.mission.memberships.filter(user=self.friend).exists())
        self.assertEqual(Invitation.objects.get().status,'accepted')
        self.assertEqual(self.client.get(self.url('updates')).status_code,200)

    def test_invitation_decline_duplicates_and_notification_route(self):
        self.client.force_login(self.owner)
        self.client.post(self.url('invite'),{'username':'friend'})
        self.client.post(self.url('invite'),{'username':'friend'})
        self.assertEqual(Invitation.objects.count(),1)
        self.assertEqual(Notification.objects.filter(mission=self.mission).count(),1)
        self.assertEqual(self.client.post(self.url('invite'),{'username':'host'}).status_code,400)
        self.assertEqual(self.client.post(self.url('invite'),{'username':'missing'}).status_code,400)
        self.client.force_login(self.friend)
        self.assertContains(self.client.get('/notifications/?kind=missions'),self.url('detail'))
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url('respond'),{'action':'accept'}).status_code,404)
        self.client.force_login(self.friend)
        self.assertEqual(self.client.post(self.url('respond'),{'action':'unknown'}).status_code,400)
        self.client.post(self.url('respond'),{'action':'decline'})
        self.assertEqual(Invitation.objects.get().status,'declined')
        self.assertFalse(self.mission.memberships.filter(user=self.friend).exists())

    def test_contribution_roundtrip_images_reactions_and_ownership(self):
        self.join()
        self.assertEqual(self.client.post(self.url('contribute'),{'text':'One perspective','image':self.image()}).status_code,302)
        entry=Contribution.objects.get()
        self.assertContains(self.client.get(self.url('contribute')),'A photo is attached')
        self.assertTrue(entry.image.storage.exists(entry.image.name))
        response=self.client.get(self.url('media',kind='entry',item_pk=entry.pk))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Cache-Control'],'private, no-store');response.close()
        self.client.post(self.url('contribute'),{'text':'Updated perspective'})
        self.assertEqual(Contribution.objects.count(),1)
        entry.refresh_from_db();self.assertEqual(entry.text,'Updated perspective')
        self.assertEqual(self.client.post(self.url('react',contribution_pk=entry.pk)).json(),{'active':True,'count':1})
        self.assertEqual(self.client.post(self.url('react',contribution_pk=entry.pk)).json(),{'active':False,'count':0})
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('delete_contribution')).status_code,404)
        self.client.force_login(self.friend)
        self.assertEqual(self.client.post(self.url('delete_contribution')).status_code,302)
        self.assertFalse(Contribution.objects.exists())

    def test_private_files_cannot_be_served_by_public_media_or_outsiders(self):
        self.mission.visibility='invite';self.mission.cover.save('cover.png',self.image());self.mission.save()
        entry=Contribution.objects.create(mission=self.mission,author=self.owner,text='Secret',image=self.image())
        for kind,key in [('cover',self.mission.pk),('entry',entry.pk)]:
            self.assertEqual(self.client.get(self.url('media',kind=kind,item_pk=key)).status_code,404)
        self.client.force_login(self.owner)
        response=self.client.get(self.url('media',kind='cover',item_pk=self.mission.pk));self.assertEqual(response.status_code,200);response.close()
        self.assertNotEqual(entry.image.storage.location,str(__import__('django.conf',fromlist=['settings']).settings.MEDIA_ROOT))
        with self.assertRaises(ValueError): _=entry.image.url
        self.client.logout()
        self.assertEqual(self.client.get(self.url('media',kind='entry',item_pk=entry.pk)).status_code,302)

    def test_invalid_image_and_empty_contribution_are_rejected(self):
        self.join()
        self.assertContains(self.client.post(self.url('contribute'),{'text':' '}),'Add a photo or a few words')
        bad=SimpleUploadedFile('bad.jpg',b'not a photo',content_type='image/jpeg')
        self.assertEqual(self.client.post(self.url('contribute'),{'text':'x','image':bad}).status_code,200)
        self.assertFalse(Contribution.objects.exists())

    def test_finish_freezes_collection_but_keeps_discussion_and_reactions(self):
        self.join();self.client.post(self.url('contribute'),{'text':'Finished perspective'})
        entry=Contribution.objects.get()
        self.client.force_login(self.owner);self.client.post(self.url('close'));self.client.post(self.url('close'))
        self.mission.refresh_from_db();self.assertTrue(self.mission.is_closed)
        self.assertEqual(Notification.objects.filter(verb='finished your shared mission').count(),1)
        self.client.force_login(self.friend)
        self.assertContains(self.client.get(self.url('detail')),'Our finished collection')
        for action,data in [('contribute',{'text':'overwrite'}),('delete_contribution',{}),('invite',{'username':'other'}),('join',{})]:
            self.assertEqual(self.client.post(self.url(action),data).status_code,400)
        self.assertEqual(self.client.post(self.url('discuss'),{'text':'Loved making this.'}).status_code,302)
        self.assertTrue(self.client.post(self.url('react',contribution_pk=entry.pk)).json()['active'])
        entry.refresh_from_db();self.assertEqual(entry.text,'Finished perspective')

    def test_deadline_reveal_needs_no_background_job(self):
        future=self.mission.ends_at+timedelta(seconds=1)
        with patch('django.utils.timezone.now',return_value=future):
            self.assertTrue(self.client.get(self.url('updates')).json()['closed'])
            self.assertContains(self.client.get(self.url('detail')),'Our finished collection')
            self.assertEqual(self.join().status_code,400)
            self.assertContains(self.client.get(reverse('missions:board')+'?tab=finished'),self.mission.title)
            self.assertNotContains(self.client.get(reverse('missions:board')),self.mission.title)

    def test_discussion_escaping_and_ownership(self):
        self.assertEqual(self.client.post(self.url('discuss'),{'text':'No membership'}).status_code,404)
        self.join();self.client.post(self.url('discuss'),{'text':'<script>unsafe()</script>'})
        comment=Discussion.objects.get()
        self.assertContains(self.client.get(self.url('detail')),'&lt;script&gt;unsafe()&lt;/script&gt;')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url('delete_discussion',comment_pk=comment.pk)).status_code,404)
        self.client.force_login(self.friend)
        self.assertEqual(self.client.post(self.url('delete_discussion',comment_pk=comment.pk)).status_code,302)

    def test_csrf_authentication_and_database_constraints(self):
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.friend)
        for action in ['join','close','invite','contribute','discuss','respond','delete_contribution']:
            self.assertEqual(secure.post(self.url(action)).status_code,403)
        anonymous=Client()
        self.assertEqual(anonymous.get(reverse('missions:board')).status_code,302)
        self.assertEqual(anonymous.post(self.url('join')).status_code,302)
        with self.assertRaises(IntegrityError),transaction.atomic():
            Membership.objects.create(mission=self.mission,user=self.owner)
        entry=Contribution.objects.create(mission=self.mission,author=self.owner,text='One')
        with self.assertRaises(IntegrityError),transaction.atomic():
            Contribution.objects.create(mission=self.mission,author=self.owner,text='Two')
        Reaction.objects.create(contribution=entry,user=self.owner)
        with self.assertRaises(IntegrityError),transaction.atomic():
            Reaction.objects.create(contribution=entry,user=self.owner)

    def test_search_filters_pagination_and_new_home_entry(self):
        for i in range(10):
            Mission.objects.create(owner=self.owner,title=f'Photography mission {i}',prompt='A new view',ends_at=timezone.now()+timedelta(days=1))
        response=self.client.get(reverse('missions:board')+'?q=Photography')
        self.assertEqual(response.context['page'].paginator.count,10)
        self.assertContains(response,'q=Photography&amp;page=2')
        self.assertEqual(len(self.client.get(reverse('missions:board')+'?q=Photography&page=2').context['page']),1)
        self.assertContains(self.client.get('/'),'Make something together')
        self.assertContains(self.client.get(reverse('missions:board')+'?tab=mine'),'Be the first')

    def test_demo_command_is_repeatable_and_preserves_changes(self):
        from django.core.management import call_command
        from io import StringIO
        for name in ['alex','zola','kai','mia','leo']:
            User.objects.create_user(name)
        call_command('seed_missions',stdout=StringIO())
        sizes=[model.objects.count() for model in [Mission,Membership,Contribution,Discussion,Reaction,Invitation,Notification]]
        demo=Mission.objects.get(title='Your city, one colour')
        demo.closed_at=timezone.now();demo.save()
        files=set(__import__('pathlib').Path(self.temporary.name).rglob('*'))
        call_command('seed_missions',stdout=StringIO())
        self.assertEqual(sizes,[model.objects.count() for model in [Mission,Membership,Contribution,Discussion,Reaction,Invitation,Notification]])
        self.assertEqual(files,set(__import__('pathlib').Path(self.temporary.name).rglob('*')))
        demo.refresh_from_db();self.assertTrue(demo.is_closed)
