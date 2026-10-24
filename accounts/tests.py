from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from posts.models import Post, Comment
from social.models import Follow, Like
from notifications.models import Notification
from chat.models import Conversation, Message
from .forms import ProfileForm

class PlatformTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a=User.objects.create_user('alice',password='A-strong-pass-42!')
        self.b=User.objects.create_user('bob',password='A-strong-pass-42!')
        self.c=User.objects.create_user('outsider',password='A-strong-pass-42!')
        self.post=Post.objects.create(author=self.b,text='Hello world')
        self.client.force_login(self.a)
    def test_anonymous_authentication_and_signup(self):
        client=Client()
        self.assertEqual(client.get('/').status_code,302)
        response=client.post('/signup/',{'username':'newperson','password1':'Unique-password-672!','password2':'Unique-password-672!'})
        self.assertEqual(response.status_code,302)
        user=User.objects.get(username='newperson')
        self.assertTrue(user.check_password('Unique-password-672!'))
        self.assertNotEqual(user.password,'Unique-password-672!')
        self.assertTrue(hasattr(user,'profile'))
        self.assertEqual(client.post('/logout/').status_code,302)
        self.assertEqual(client.post('/login/',{'username':'newperson','password':'Unique-password-672!'}).status_code,302)
    def test_like_and_follow_toggle_notifications(self):
        url=f'/posts/{self.post.pk}/like/'
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertTrue(self.client.post(url).json()['active'])
        self.assertEqual(Like.objects.count(),1)
        self.assertFalse(self.client.post(url).json()['active'])
        self.assertEqual(Like.objects.count(),0)
        self.assertEqual(self.client.post('/u/alice/follow/').status_code,400)
        self.assertTrue(self.client.post('/u/bob/follow/').json()['active'])
        self.assertEqual(Follow.objects.count(),1)
        self.assertFalse(self.client.post('/u/bob/follow/').json()['active'])
        self.assertEqual(Follow.objects.count(),0)
        self.assertEqual(Notification.objects.filter(recipient=self.b).count(),2)
    def test_ownership_post_and_comment(self):
        self.assertEqual(self.client.post(f'/posts/{self.post.pk}/edit/',{'text':'hacked'}).status_code,404)
        self.assertEqual(self.client.post(f'/posts/{self.post.pk}/delete/').status_code,404)
        comment=Comment.objects.create(author=self.b,post=self.post,text='Protected')
        self.assertEqual(self.client.post(f'/comments/{comment.pk}/delete/').status_code,404)
        self.assertEqual(self.client.post(f'/comments/{comment.pk}/edit/',{'text':'hacked'}).status_code,404)
        self.client.post('/',{'text':'My own post'})
        own=Post.objects.get(author=self.a)
        self.assertEqual(self.client.post(f'/posts/{own.pk}/edit/',{'text':'Changed'}).status_code,302)
        own.refresh_from_db();self.assertEqual(own.text,'Changed')
        self.assertEqual(self.client.post(f'/posts/{own.pk}/delete/').status_code,302)
    def test_feed_comments_and_page_rendering(self):
        self.assertNotContains(self.client.get('/'),'Hello world')
        self.client.post('/u/bob/follow/')
        self.assertContains(self.client.get('/'),'Hello world')
        response=self.client.post(f'/posts/{self.post.pk}/',{'text':'Great post'})
        self.assertEqual(response.status_code,302)
        comment=Comment.objects.get(author=self.a)
        self.assertEqual(self.client.post(f'/comments/{comment.pk}/edit/',{'text':'Even better'}).status_code,302)
        for path in ['/explore/','/u/alice/','/profile/edit/','/people/?q=bob','/u/bob/followers/','/u/bob/following/','/messages/','/notifications/',f'/posts/{self.post.pk}/']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertEqual(self.client.post(f'/comments/{comment.pk}/delete/').status_code,302)
        self.assertEqual(self.post.comments.count(),0)
    def test_chat_access_and_unread(self):
        self.client.post('/messages/start/bob/')
        room=Conversation.objects.get()
        self.client.post('/messages/start/bob/')
        self.assertEqual(Conversation.objects.count(),1)
        Message.objects.create(conversation=room,sender=self.b,text='Private hello')
        self.assertEqual(self.client.get(f'/messages/{room.pk}/history/').json()['messages'][0]['text'],'Private hello')
        self.assertFalse(Message.objects.get().read)
        self.client.post(f'/messages/{room.pk}/read/', {'up_to':Message.objects.get().pk})
        self.assertTrue(Message.objects.get().read)
        self.client.force_login(self.c)
        self.assertEqual(self.client.get(f'/messages/{room.pk}/').status_code,404)
        self.assertEqual(self.client.get(f'/messages/{room.pk}/history/').status_code,404)
    def test_csrf_and_upload_validation(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.a)
        self.assertEqual(client.post('/u/bob/follow/').status_code,403)
        form=ProfileForm(data={'display_name':'Alice'},files={'avatar':SimpleUploadedFile('x.png',b'not an image',content_type='image/png')},instance=self.a.profile)
        self.assertFalse(form.is_valid())
        self.assertEqual(self.client.post('/',{'text':''}).status_code,200)
        self.assertEqual(Post.objects.count(),1)
    def test_rate_limit(self):
        from accounts.middleware import limited
        self.assertFalse(limited('test',1))
        self.assertTrue(limited('test',1))
    def test_database_guards(self):
        from django.db import IntegrityError, transaction
        Follow.objects.create(source=self.a,target=self.b)
        for operation in [lambda:Follow.objects.create(source=self.a,target=self.b),lambda:Follow.objects.create(source=self.a,target=self.a),lambda:Conversation.objects.create(a=self.b,b=self.a)]:
            with self.assertRaises(IntegrityError), transaction.atomic(): operation()
        Like.objects.create(user=self.a,post=self.post)
        with self.assertRaises(IntegrityError), transaction.atomic(): Like.objects.create(user=self.a,post=self.post)
    def test_chat_pagination_and_notification_ownership(self):
        room=Conversation.objects.create(a=self.a,b=self.b)
        for i in range(35): Message.objects.create(conversation=room,sender=self.b,text=f'Message {i}')
        data=self.client.get(f'/messages/{room.pk}/history/').json()
        self.assertEqual(len(data['messages']),30);self.assertTrue(data['more'])
        older=self.client.get(f'/messages/{room.pk}/history/?before={data["messages"][0]["id"]}').json()
        self.assertEqual(len(older['messages']),5);self.assertFalse(older['more'])
        notice=Notification.objects.create(recipient=self.b,actor=self.a,verb='test')
        self.client.post('/notifications/');notice.refresh_from_db();self.assertFalse(notice.read)
    def test_profile_collection_and_discovery(self):
        response=self.client.get('/u/bob/')
        self.assertContains(response,'profile-grid',status_code=200)
        self.assertEqual(response.context['photo_count'],0)
        self.assertEqual(response.context['total_likes'],0)
        discovery=self.client.get('/people/')
        self.assertContains(discovery,'bob')
        self.assertNotIn(self.a,list(discovery.context['people']))
        self.assertContains(self.client.get('/explore/'),'explore-grid')
    def test_discover_search_filters_sort_and_pagination(self):
        photos=[Post.objects.create(author=self.b,text=f'Sunrise frame {i}',image=f'posts/frame-{i}.jpg') for i in range(11)]
        Like.objects.create(user=self.a,post=photos[0])
        response=self.client.get('/explore/?q=sunrise&type=photos&sort=popular')
        self.assertEqual(response.context['discover_total'],11)
        self.assertEqual(response.context['featured'],photos[0])
        self.assertEqual(response.context['page'][0],photos[0])
        self.assertContains(response,'type=photos&amp;sort=popular&amp;q=sunrise&amp;page=2')
        thoughts=self.client.get('/explore/?type=thoughts')
        self.assertEqual(thoughts.context['discover_total'],1)
        self.assertIsNone(thoughts.context['featured'])
        self.assertEqual(thoughts.context['page'][0],self.post)
        empty=self.client.get('/explore/?q=no-matching-caption')
        self.assertContains(empty,'No moments found yet.')
