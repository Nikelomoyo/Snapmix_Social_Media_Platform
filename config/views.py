from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Max, Count
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from urllib.parse import urlencode
from accounts.forms import SignupForm, ProfileForm, InterestsForm
from accounts.topics import TOPICS
from posts.recommendations import rank_posts, explain_posts
from posts.models import Post, Comment
from posts.forms import PostForm, CommentForm
from social.models import Like, Follow
from notifications.models import Notification
from chat.models import Conversation, Message

def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        return redirect('interests')
    return render(request, 'form.html', {'form':form,'title':'Find your people.','subtitle':'A little snap. A lot of connection.','signup':True})

def notify(recipient, actor, verb, post=None):
    if recipient != actor:
        Notification.objects.create(recipient=recipient, actor=actor, verb=verb, post=post)

def post_list(request, queryset):
    page = Paginator(queryset.select_related('author__profile').prefetch_related('likes','comments'), 10).get_page(request.GET.get('page'))
    liked = set(Like.objects.filter(user=request.user, post__in=page.object_list).values_list('post_id', flat=True))
    return page, liked

@login_required
def feed(request, explore=False):
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False); post.author=request.user; post.save()
        return redirect('home')
    queryset = Post.objects.all()
    feed_view=request.GET.get('view','for-you' if request.user.profile.interests else 'following')
    feed_view=feed_view if feed_view in ('for-you','following') else 'following'
    if not explore:
        if feed_view=='following':
            queryset=queryset.filter(Q(author=request.user)|Q(author_id__in=request.user.following.values('target_id')))
        else:
            queryset=rank_posts(queryset,request.user)
    if explore:
        kind=request.GET.get('type','all')
        kind=kind if kind in ('all','photos','thoughts') else 'all'
        sort=request.GET.get('sort','for-you' if request.user.profile.interests else 'latest')
        sort=sort if sort in ('latest','popular','for-you') else 'latest'
        query=request.GET.get('q','').strip()[:100]
        if query:
            queryset=queryset.filter(Q(text__icontains=query)|Q(author__username__icontains=query)|Q(author__profile__display_name__icontains=query))
        if kind=='photos': queryset=queryset.exclude(image='')
        if kind=='thoughts': queryset=queryset.filter(image='')
        if sort=='popular': queryset=queryset.annotate(reaction_count=Count('likes',distinct=True)).order_by('-reaction_count','-created_at','-pk')
        if sort=='for-you': queryset=rank_posts(queryset,request.user)
        total=queryset.count()
        featured=queryset.exclude(image='').select_related('author__profile').first() if not request.GET.get('page') else None
        # The feature is repeated in the complete gallery so later pages never skip a post.
        page,liked=post_list(request,queryset)
        if sort=='for-you': explain_posts(page,request.user)
        return render(request,'discover.html',{'page':page,'liked':liked,'featured':featured,'kind':kind,'sort':sort,'query':query,'discover_total':total,'title':'Discover','pagination_query':urlencode({'type':kind,'sort':sort,'q':query})+'&'})
    page, liked = post_list(request, queryset)
    if feed_view=='for-you': explain_posts(page,request.user)
    return render(request,'feed.html',{'page':page,'liked':liked,'form':form,'explore':explore,'feed_view':feed_view,'pagination_query':urlencode({'view':feed_view})+'&','title':'Your daily mix'})

@login_required
def interests(request):
    profile=request.user.profile
    form=InterestsForm(request.POST if request.method=='POST' else None,initial={'interests':profile.interests,'learn_from_activity':profile.learn_from_activity})
    if request.method=='POST':
        if request.POST.get('action')=='skip':
            profile.interests=[];profile.interests_set=True;profile.learn_from_activity=False
            profile.save(update_fields=['interests','interests_set','learn_from_activity'])
            return redirect('home')
        if form.is_valid():
            profile.interests=form.cleaned_data['interests'];profile.interests_set=True
            profile.learn_from_activity=form.cleaned_data['learn_from_activity']
            profile.save(update_fields=['interests','interests_set','learn_from_activity'])
            return redirect('/?view=for-you')
    chosen=set(form.data.getlist('interests') if form.is_bound else profile.interests)
    topics=[{'key':key,'label':label,'photo':photo,'symbol':symbol,'selected':key in chosen} for key,label,photo,symbol in TOPICS]
    return render(request,'interests.html',{'form':form,'topics':topics,'chosen_count':len(chosen),'title':'Make it your mix'})

@login_required
def profile(request, username):
    person = get_object_or_404(User.objects.select_related('profile'), username=username)
    page, liked = post_list(request, person.posts.all())
    photos=person.posts.exclude(image='')
    return render(request,'profile.html',{'person':person,'page':page,'liked':liked,'following':Follow.objects.filter(source=request.user,target=person).exists(),'title':person.profile.name,'cover_post':photos.first(),'photo_count':photos.count(),'total_likes':Like.objects.filter(post__author=person).count(),'profile_photos':photos[:4]})

@login_required
def edit_profile(request):
    form=ProfileForm(request.POST or None, request.FILES or None, instance=request.user.profile)
    if request.method=='POST' and form.is_valid():
        form.save(); return redirect('profile', username=request.user.username)
    return render(request,'form.html',{'form':form,'title':'Make it yours'})

@login_required
def search(request):
    query=request.GET.get('q','').strip()[:100]
    people=User.objects.exclude(pk=request.user.pk).select_related('profile').prefetch_related('posts').annotate(post_total=Count('posts'))
    people=people.filter(Q(username__icontains=query)|Q(profile__display_name__icontains=query)) if query else people.order_by('-post_total','username')
    people=people[:40]
    return render(request,'people.html',{'people':people,'title':'Find your people','query':query,'search':True})

@login_required
def connections(request, username, kind):
    person=get_object_or_404(User,username=username)
    people=User.objects.filter(pk__in=(person.followers.values('source_id') if kind=='followers' else person.following.values('target_id'))).select_related('profile')
    return render(request,'people.html',{'people':people,'title':f'{person.username} · {kind}'})

@login_required
@require_POST
def like(request, pk):
    post=get_object_or_404(Post,pk=pk)
    obj, created=Like.objects.get_or_create(user=request.user,post=post)
    if not created: obj.delete()
    else: notify(post.author,request.user,'liked your post',post)
    return JsonResponse({'active':created,'count':post.likes.count()})

@login_required
@require_POST
def follow(request, username):
    target=get_object_or_404(User,username=username)
    if target==request.user: return HttpResponseBadRequest('You cannot follow yourself.')
    obj,created=Follow.objects.get_or_create(source=request.user,target=target)
    if not created: obj.delete()
    else: notify(target,request.user,'started following you')
    return JsonResponse({'active':created,'count':target.followers.count()})

@login_required
def detail(request, pk):
    post=get_object_or_404(Post.objects.select_related('author__profile'),pk=pk)
    form=CommentForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        comment=form.save(commit=False); comment.post=post; comment.author=request.user; comment.save()
        notify(post.author,request.user,'commented on your post',post)
        return redirect('detail',pk=pk)
    return render(request,'detail.html',{'post':post,'liked':set(Like.objects.filter(user=request.user,post=post).values_list('post_id',flat=True)),'form':form,'title':'The conversation'})

@login_required
def edit_content(request, pk, comment=False):
    obj=get_object_or_404(Comment if comment else Post,pk=pk,author=request.user)
    form=(CommentForm if comment else PostForm)(request.POST or None, request.FILES or None, instance=obj)
    if request.method=='POST' and form.is_valid():
        form.save(); return redirect('detail',pk=obj.post_id if comment else obj.pk)
    return render(request,'form.html',{'form':form,'title':'Edit comment' if comment else 'Edit post'})

@login_required
@require_POST
def delete_content(request, pk, comment=False):
    obj=get_object_or_404(Comment if comment else Post,pk=pk,author=request.user)
    target=obj.post_id if comment else None
    obj.delete()
    return redirect('detail',pk=target) if target else redirect('home')

@login_required
def notifications(request):
    kind=request.GET.get('kind','all')
    kind=kind if kind in ('all','unread','likes','comments','follows','missions') else 'all'
    notices=request.user.notifications.all()
    if request.method=='POST':
        if request.POST.get('action')=='one':
            notice_id=request.POST.get('notice_id','')
            if not notice_id.isdigit(): return HttpResponseBadRequest('Invalid notification')
            notice=get_object_or_404(notices,pk=notice_id)
            notice.read=True;notice.save(update_fields=['read'])
        else:
            notices.filter(read=False).update(read=True)
        return redirect(reverse('notifications')+'?'+urlencode({'kind':kind}))
    unread=notices.filter(read=False).count()
    week=notices.filter(created_at__gte=timezone.now()-timedelta(days=7))
    metrics={'likes':week.filter(verb='liked your post').count(),'comments':week.filter(verb='commented on your post').count(),'follows':week.filter(verb='started following you').count()}
    if kind=='missions': notices=notices.filter(mission__isnull=False)
    if kind=='unread': notices=notices.filter(read=False)
    elif kind in ('likes','comments','follows'):
        notices=notices.filter(verb={'likes':'liked your post','comments':'commented on your post','follows':'started following you'}[kind])
    items=notices.select_related('actor__profile','post','mission').annotate(activity_day=TruncDate('created_at',tzinfo=timezone.get_current_timezone()))[:100]
    return render(request,'notifications.html',{'items':items,'kind':kind,'unread_count':unread,'metrics':metrics,'today':timezone.localdate(),'yesterday':timezone.localdate()-timedelta(days=1),'title':'Your activity'})

@login_required
@require_POST
def start_chat(request, username):
    other=get_object_or_404(User,username=username)
    if other==request.user: return HttpResponseBadRequest('Choose another person.')
    a,b=sorted([request.user.pk,other.pk])
    room,_=Conversation.objects.get_or_create(a_id=a,b_id=b)
    return redirect('conversation',pk=room.pk)

@login_required
def inbox(request, pk=None):
    rooms=Conversation.objects.filter(Q(a=request.user)|Q(b=request.user)).select_related('a__profile','b__profile').annotate(last_activity=Coalesce(Max('messages__created_at'),'created_at')).order_by('-last_activity','-pk')
    room=get_object_or_404(rooms,pk=pk) if pk else None
    entries=[]
    for item in rooms:
        entries.append({'room':item,'other':item.b if item.a_id==request.user.pk else item.a,'last':item.messages.last(),'unread':item.messages.filter(read=False).exclude(sender=request.user).count()})
    chat_people=User.objects.exclude(pk=request.user.pk).select_related('profile').annotate(post_total=Count('posts')).order_by('-post_total','username')[:6]
    return render(request,'chat.html',{'entries':entries,'room':room,'other':(room.b if room.a_id==request.user.pk else room.a) if room else None,'chat_people':chat_people,'inbox_unread':sum(e['unread'] for e in entries),'title':'Messages'})

@login_required
def history(request, pk):
    from chat.consumers import cursor, serialize
    room=get_object_or_404(Conversation.objects.filter(Q(a=request.user)|Q(b=request.user)),pk=pk)
    queryset=room.messages.select_related('sender')
    before,after=request.GET.get('before'),request.GET.get('after')
    if before and after: return HttpResponseBadRequest('Choose one cursor')
    try:
        if before: queryset=queryset.filter(pk__lt=cursor(before))
        if after: queryset=queryset.filter(pk__gt=cursor(after))
    except ValueError:
        return HttpResponseBadRequest('Invalid cursor')
    size=100 if after else 30
    batch=list(queryset.order_by('pk' if after else '-pk')[:size+1])
    more=len(batch)>size
    batch=batch[:size] if after else list(reversed(batch[:size]))
    return JsonResponse({'messages':[serialize(m) for m in batch],'more':more})

@login_required
@require_POST
def read_messages(request, pk):
    from chat.consumers import cursor
    room=get_object_or_404(Conversation.objects.filter(Q(a=request.user)|Q(b=request.user)),pk=pk)
    try: up_to=cursor(request.POST.get('up_to'))
    except ValueError: return HttpResponseBadRequest('Invalid cursor')
    count=room.messages.filter(pk__lte=up_to,read=False).exclude(sender=request.user).update(read=True)
    return JsonResponse({'read':count})
