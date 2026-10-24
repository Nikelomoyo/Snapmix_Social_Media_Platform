"""Explainable local ranking, with no external model or private-message analysis."""
from collections import Counter
from datetime import timedelta
from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone
from accounts.topics import TOPIC_NAMES
from social.models import Like
from .models import Comment

def topic_weights(user):
    profile=user.profile
    weights=Counter({topic:8 for topic in profile.interests if topic in TOPIC_NAMES})
    if profile.learn_from_activity:
        likes=Counter(Like.objects.filter(user=user).order_by('-created_at').values_list('post__topic',flat=True)[:200])
        comments=Counter(Comment.objects.filter(author=user).order_by('-created_at').values_list('post__topic',flat=True)[:100])
        for topic in TOPIC_NAMES:
            weights[topic]+=min(likes[topic]*2,6)+min(comments[topic]*3,6)
    return weights

def rank_posts(queryset,user):
    weights=topic_weights(user)
    topic_score=Case(*[When(topic=topic,then=Value(weight)) for topic,weight in weights.items() if weight],default=Value(0),output_field=IntegerField())
    circle_score=Case(When(author_id__in=user.following.values('target_id'),then=Value(2)),default=Value(0),output_field=IntegerField())
    now=timezone.now()
    freshness=Case(When(created_at__gte=now-timedelta(days=1),then=Value(2)),When(created_at__gte=now-timedelta(days=7),then=Value(1)),default=Value(0),output_field=IntegerField())
    return queryset.annotate(interest_score=topic_score+circle_score+freshness).order_by('-interest_score','-created_at','-pk')

def explain_posts(page,user):
    selected=set(user.profile.interests)
    weights=topic_weights(user)
    followed=set(user.following.values_list('target_id',flat=True))
    for post in page:
        if post.topic in selected:
            post.recommendation_reason=f'Because you chose {TOPIC_NAMES[post.topic]}'
        elif weights[post.topic]:
            post.recommendation_reason='Inspired by topics you’ve liked or discussed'
        elif post.author_id in followed:
            post.recommendation_reason='From someone you follow'
        else:
            post.recommendation_reason='A fresh perspective to explore'
