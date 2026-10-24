from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from posts.models import Post, Comment
from posts.recommendations import rank_posts
from social.models import Like, Follow
from notifications.models import Notification

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PersonalizationAndHubTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=User.objects.create_user('reader',password='test-password')
        self.author=User.objects.create_user('creator',password='test-password')
        self.stranger=User.objects.create_user('stranger',password='test-password')
        self.client.force_login(self.user)

    def test_interest_choices_are_validated_and_persisted(self):
        response=self.client.post('/interests/',{'interests':['nature','food'],'learn_from_activity':'on'})
        self.assertRedirects(response,'/?view=for-you')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.interests,['nature','food'])
        self.assertTrue(self.user.profile.interests_set)
        self.assertTrue(self.user.profile.learn_from_activity)
        response=self.client.post('/interests/',{'interests':['not-a-topic']})
        self.assertEqual(response.status_code,200)
        self.assertIn('interests',response.context['form'].errors)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.interests,['nature','food'])
        response=self.client.post('/interests/',{'interests':['travel','nature','food','photography','design','technology','music']})
        self.assertIn('interests',response.context['form'].errors)
        self.client.post('/interests/',{'action':'skip'})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.interests,[])
        self.assertFalse(self.user.profile.learn_from_activity)

    def test_interest_selection_requires_auth_and_csrf(self):
        self.assertEqual(Client().get('/interests/').status_code,302)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post('/interests/',{'interests':['nature']}).status_code,403)
        self.assertEqual(self.author.profile.interests,[])

    def test_selected_topics_change_ranking_without_filtering_other_topics(self):
        outdoors=Post.objects.create(author=self.author,text='Forest trail',topic='nature')
        Post.objects.filter(pk=outdoors.pk).update(created_at=timezone.now()-timedelta(days=10))
        technology=Post.objects.create(author=self.stranger,text='Software release',topic='technology')
        self.client.post('/interests/',{'interests':['nature']})
        feed=self.client.get('/?view=for-you')
        self.assertEqual(feed.context['page'][0],outdoors)
        self.assertContains(feed,'Because you chose Nature &amp; outdoors')
        self.assertIn(technology,list(feed.context['page']))
        discover=self.client.get('/explore/?sort=for-you')
        self.assertEqual(discover.context['page'][0],outdoors)
        # Following stays a chronological, permission-neutral alternative.
        self.assertNotContains(self.client.get('/?view=following'),'Forest trail')
        Follow.objects.create(source=self.user,target=self.author)
        self.assertContains(self.client.get('/?view=following'),'Forest trail')

    def test_activity_learning_can_be_disabled(self):
        old=Post.objects.create(author=self.author,text='A forest walk',topic='nature')
        Post.objects.filter(pk=old.pk).update(created_at=timezone.now()-timedelta(days=2))
        new=Post.objects.create(author=self.stranger,text='New software',topic='technology')
        Like.objects.create(user=self.user,post=old)
        Comment.objects.create(author=self.user,post=old,text='Love the trail')
        self.assertEqual(rank_posts(Post.objects.all(),self.user).first(),old)
        self.user.profile.learn_from_activity=False;self.user.profile.save()
        self.assertEqual(rank_posts(Post.objects.all(),self.user).first(),new)

    def test_caption_classification_and_explicit_topics(self):
        inferred=Post.objects.create(author=self.author,text='My morning coffee ritual')
        self.assertEqual(inferred.topic,'food')
        explicit=Post.objects.create(author=self.author,text='Coffee and code',topic='technology')
        self.assertEqual(explicit.topic,'technology')

    def test_activity_filters_individual_read_and_ownership(self):
        post=Post.objects.create(author=self.user,text='Weekend plans')
        like=Notification.objects.create(recipient=self.user,actor=self.author,verb='liked your post',post=post)
        follow=Notification.objects.create(recipient=self.user,actor=self.stranger,verb='started following you')
        private=Notification.objects.create(recipient=self.author,actor=self.stranger,verb='started following you')
        response=self.client.get('/notifications/?kind=likes')
        self.assertEqual(list(response.context['items']),[like])
        self.assertEqual(response.context['metrics']['likes'],1)
        self.assertEqual(response.context['metrics']['follows'],1)
        self.assertEqual(response.context['unread_count'],2)
        self.assertEqual(self.client.post('/notifications/',{'action':'one','notice_id':private.pk}).status_code,404)
        self.client.post('/notifications/?kind=unread',{'action':'one','notice_id':like.pk})
        like.refresh_from_db();follow.refresh_from_db();private.refresh_from_db()
        self.assertTrue(like.read);self.assertFalse(follow.read);self.assertFalse(private.read)
        self.assertEqual(list(self.client.get('/notifications/?kind=unread').context['items']),[follow])

    def test_rich_hubs_and_empty_states_render(self):
        for url in ['/messages/','/notifications/','/interests/']:
            self.assertEqual(self.client.get(url).status_code,200)
        self.assertContains(self.client.get('/messages/'),'Something to talk about.')
        self.assertContains(self.client.get('/notifications/'),'A new connection starts somewhere.')
        self.client.post('/messages/start/creator/')
        room=self.user.conversations_a.first() or self.user.conversations_b.first()
        response=self.client.get(f'/messages/{room.pk}/')
        self.assertContains(response,'Conversation starters')
        self.assertContains(response,'emoji-toggle')
