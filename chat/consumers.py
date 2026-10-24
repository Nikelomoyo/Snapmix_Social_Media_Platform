import json
from uuid import UUID
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Q
from accounts.middleware import limited
from .models import Conversation, Message
def cursor(value):
    value=str(value)
    if not value.isascii() or not value.isdigit() or len(value)>19:
        raise ValueError('Invalid cursor')
    number=int(value)
    if not 0<number<=9223372036854775807: raise ValueError('Invalid cursor')
    return number

def serialize(m):
    return {'id':m.pk,'text':m.text,'sender':m.sender.username,'time':m.created_at.isoformat(),'client_id':str(m.client_id) if m.client_id else None}

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_id=self.scope['url_route']['kwargs']['pk']
        self.user=self.scope['user']
        self.group=f'conversation_{self.room_id}'
        if not self.user.is_authenticated or not await self.allowed():
            await self.close(code=4403); return
        await self.channel_layer.group_add(self.group,self.channel_name)
        await self.accept()
    @database_sync_to_async
    def allowed(self):
        return Conversation.objects.filter(pk=self.room_id).filter(Q(a=self.user)|Q(b=self.user)).exists()
    @database_sync_to_async
    def save_message(self,text,client_id):
        if not Conversation.objects.filter(pk=self.room_id).filter(Q(a=self.user)|Q(b=self.user)).exists(): return None
        lookup={'conversation_id':self.room_id,'sender':self.user,'client_id':client_id}
        if client_id:
            previous=Message.objects.filter(**lookup).select_related('sender').first()
            if previous: return serialize(previous)
        if limited(f'chat:{self.user.pk}',30): return None
        if client_id: m,_=Message.objects.get_or_create(**lookup,defaults={'text':text})
        else: m=Message.objects.create(**lookup,text=text)
        return serialize(m)
    async def receive(self,text_data=None,bytes_data=None,**kwargs):
        if text_data is None or len(text_data)>24000:
            await self.send_json({'error':'Invalid message frame.'}); return
        try: content=json.loads(text_data)
        except (ValueError,RecursionError):
            await self.send_json({'error':'Invalid JSON.'}); return
        await self.receive_json(content)
    async def receive_json(self,content):
        if not isinstance(content,dict):
            await self.send_json({'error':'Invalid message.'}); return
        if content.get('type')=='read':
            try: up_to=cursor(content.get('up_to'))
            except ValueError:
                await self.send_json({'error':'Invalid read cursor.'}); return
            await self.mark_read(up_to); return
        text=content.get('text','')
        if not isinstance(text,str) or not text.strip() or len(text)>2000:
            await self.send_json({'error':'Messages need 1–2000 characters.'}); return
        try: client_id=UUID(str(content['client_id'])) if content.get('client_id') else None
        except (ValueError,TypeError,AttributeError):
            await self.send_json({'error':'Invalid message identifier.'}); return
        result=await self.save_message(text.strip(),client_id)
        if result is None:
            await self.send_json({'error':'Message limit reached. Try again shortly.'}); return
        await self.channel_layer.group_send(self.group,{'type':'chat.message','message':result})
    @database_sync_to_async
    def mark_read(self,up_to):
        Message.objects.filter(conversation_id=self.room_id,pk__lte=up_to,read=False).exclude(sender=self.user).update(read=True)
    async def chat_message(self,event): await self.send_json(event['message'])
    async def disconnect(self,code):
        if hasattr(self,'group'): await self.channel_layer.group_discard(self.group,self.channel_name)
