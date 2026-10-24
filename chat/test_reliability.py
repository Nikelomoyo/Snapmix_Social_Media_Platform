from uuid import uuid4
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TransactionTestCase, override_settings
from config.asgi import application
from .models import Conversation, Message


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReliabilityTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.a=User.objects.create_user('sender',password='test-password')
        self.b=User.objects.create_user('recipient',password='test-password')
        self.c=User.objects.create_user('outsider',password='test-password')
        self.room=Conversation.objects.create(a=self.a,b=self.b)
        self.client.force_login(self.a)

    def socket(self, user=None, origin='http://testserver'):
        headers=[(b'origin',origin.encode())]
        if user:
            client=Client();client.force_login(user)
            headers.append((b'cookie',f'sessionid={client.cookies["sessionid"].value}'.encode()))
        return WebsocketCommunicator(application,f'/ws/chat/{self.room.pk}/',headers=headers)

    def test_real_session_authentication_origin_and_retry(self):
        # Build sessions synchronously before entering the async event loop.
        rejected=[self.socket(),self.socket(self.c),self.socket(self.a,'https://evil.invalid')]
        a,b=self.socket(self.a),self.socket(self.b)
        token=str(uuid4())
        async def scenario():
            for socket in rejected:
                self.assertFalse((await socket.connect())[0]);await socket.disconnect()
            self.assertTrue((await a.connect())[0]);self.assertTrue((await b.connect())[0])
            for raw in ['{broken','[]']:
                await a.send_to(text_data=raw)
                self.assertIn('error',await a.receive_json_from())
            for payload in [{'text':'x','client_id':'bad'}, {'text':'x'*2001}]:
                await a.send_json_to(payload)
                self.assertIn('error',await a.receive_json_from())
            ids=[]
            for _ in range(2):
                await a.send_json_to({'text':'One persisted message','client_id':token})
                mine,theirs=await a.receive_json_from(),await b.receive_json_from()
                self.assertEqual(mine['id'],theirs['id']);ids.append(mine['id'])
                self.assertEqual(mine['client_id'],token)
            self.assertEqual(ids[0],ids[1])
            await b.send_json_to({'type':'read','up_to':ids[0]})
            # A subsequent reply confirms the preceding read frame was processed.
            await b.send_json_to({'text':'Read it'})
            await b.receive_json_from();await a.receive_json_from()
            await a.disconnect();await b.disconnect()
        async_to_sync(scenario)()
        self.assertEqual(Message.objects.count(),2)
        self.assertTrue(Message.objects.get(client_id=token).read)

    def test_catchup_pagination_and_explicit_read_permissions(self):
        messages=Message.objects.bulk_create([Message(conversation=self.room,sender=self.b,text=str(i)) for i in range(145)])
        url=f'/messages/{self.room.pk}/'
        self.client.get(url);self.client.get(url+'history/')
        self.assertFalse(self.room.messages.filter(read=True).exists())
        first=self.client.get(url+f'history/?after={messages[0].pk}').json()
        self.assertEqual(len(first['messages']),100);self.assertTrue(first['more'])
        rest=self.client.get(url+f'history/?after={first["messages"][-1]["id"]}').json()
        self.assertEqual(len(rest['messages']),44);self.assertFalse(rest['more'])
        self.assertEqual(self.client.get(url+'read/').status_code,405)
        for value in ['-1','0','9'*80,'invalid','١']:
            self.assertEqual(self.client.get(url+'history/',{'before':value}).status_code,400)
            self.assertEqual(self.client.post(url+'read/',{'up_to':value}).status_code,400)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.a)
        self.assertEqual(secure.post(url+'read/',{'up_to':messages[0].pk}).status_code,403)
        self.assertEqual(self.client.post(url+'read/',{'up_to':messages[0].pk}).json()['read'],1)
        self.assertEqual(self.room.messages.filter(read=True).count(),1)
        self.client.force_login(self.c)
        self.assertEqual(self.client.post(url+'read/',{'up_to':messages[-1].pk}).status_code,404)
