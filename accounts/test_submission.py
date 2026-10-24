from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from posts.models import Post


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SubmissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=User.objects.create_user('intern',password='test-password')
        self.client.force_login(self.user)

    def image(self):
        data=BytesIO();Image.new('RGB',(24,24),'blue').save(data,format='PNG')
        return SimpleUploadedFile('sample.png',data.getvalue(),content_type='image/png')

    def test_profile_and_image_post_round_trip_and_escaping(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response=self.client.post('/profile/edit/',{'display_name':'Intern Demo','bio':'<script>bad()</script>','location':'Cape Town','avatar':self.image()})
            self.assertEqual(response.status_code,302)
            self.user.profile.refresh_from_db()
            self.assertEqual(self.user.profile.display_name,'Intern Demo')
            self.assertTrue(self.user.profile.avatar.storage.exists(self.user.profile.avatar.name))
            self.assertContains(self.client.get('/u/intern/'),'&lt;script&gt;bad()&lt;/script&gt;')
            self.assertNotContains(self.client.get('/u/intern/'),'<script>bad()</script>')
            self.assertEqual(self.client.post('/',{'text':'Photo test','image':self.image()}).status_code,302)
            post=Post.objects.get(author=self.user)
            self.assertTrue(post.image.storage.exists(post.image.name))
            self.assertContains(self.client.get(f'/posts/{post.pk}/'),post.image.url)
            self.client.post(f'/posts/{post.pk}/edit/',{'text':'Updated caption','topic':'photography'})
            post.refresh_from_db();self.assertEqual(post.text,'Updated caption')
            self.assertTrue(post.image)

    def test_authentication_and_write_rate_limits_are_applied(self):
        # Middleware integration: counting helper alone would not catch unwired limits.
        for _ in range(15):
            self.assertNotEqual(self.client.post('/login/',{'username':'missing','password':'wrong'}).status_code,429)
        self.assertEqual(self.client.post('/login/',{'username':'missing','password':'wrong'}).status_code,429)
        cache.clear()
        for _ in range(60):
            self.assertEqual(self.client.post('/notifications/').status_code,302)
        self.assertEqual(self.client.post('/notifications/').status_code,429)
