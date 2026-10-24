from django.contrib.auth.models import User
from chat.models import Message
from posts.models import Post
from django.db.models import Count
from .topics import TOPIC_NAMES
def sidebar(request):
    if not request.user.is_authenticated: return {}
    return {'interest_labels':[TOPIC_NAMES[key] for key in request.user.profile.interests if key in TOPIC_NAMES], 'suggestions':User.objects.exclude(pk=request.user.pk).exclude(pk__in=request.user.following.values('target_id')).select_related('profile')[:4], 'community_people':User.objects.select_related('profile').annotate(post_total=Count('posts')).filter(post_total__gt=0).order_by('-post_total','username')[:8], 'community_photos':Post.objects.exclude(image='').select_related('author__profile')[:6], 'notification_unread':request.user.notifications.filter(read=False).count(), 'chat_unread':Message.objects.filter(conversation__in=request.user.conversations_a.all() | request.user.conversations_b.all(), read=False).exclude(sender=request.user).count()}
