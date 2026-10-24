from django.test import TransactionTestCase
from django.contrib.auth.models import User, AnonymousUser
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import path
from asgiref.sync import async_to_sync
from django.core.cache import cache
from .consumers import ChatConsumer
from .models import Conversation, Message

class SocketTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.a=User.objects.create_user('a');self.b=User.objects.create_user('b');self.c=User.objects.create_user('c')
        self.room=Conversation.objects.create(a=self.a,b=self.b)
    def communicator(self,user):
        c=WebsocketCommunicator(URLRouter([path('ws/chat/<int:pk>/',ChatConsumer.as_asgi())]),f'/ws/chat/{self.room.pk}/')
        c.scope['user']=user
        return c
    def test_access_and_delivery(self):
        async def scenario():
            for user in [AnonymousUser(),self.c]:
                outsider=self.communicator(user)
                connected,_=await outsider.connect();self.assertFalse(connected)
                await outsider.disconnect()
            a=self.communicator(self.a);b=self.communicator(self.b)
            self.assertTrue((await a.connect())[0]);self.assertTrue((await b.connect())[0])
            await a.send_json_to({'text':'hello <script>alert(1)</script>'})
            own=await a.receive_json_from();other=await b.receive_json_from()
            self.assertEqual(own['id'],other['id']);self.assertEqual(other['sender'],'a')
            await a.send_json_to({'text':' '})
            self.assertIn('error',await a.receive_json_from())
            await a.disconnect();await b.disconnect()
            reconnect=self.communicator(self.b);self.assertTrue((await reconnect.connect())[0]);await reconnect.disconnect()
        async_to_sync(scenario)()
        self.assertEqual(Message.objects.count(),1)
