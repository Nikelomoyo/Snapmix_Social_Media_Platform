from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.http import Http404, HttpResponseBadRequest, JsonResponse, FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from notifications.models import Notification
from .forms import MissionForm, ContributionForm, InviteForm, DiscussionForm
from .models import Mission, Membership, Invitation, Contribution, Reaction, Discussion


def visible(user):
    return Mission.objects.filter(
        Q(visibility='public') | Q(owner=user) | Q(memberships__user=user) |
        Q(invitations__recipient=user, invitations__status='pending')
    ).distinct()


def accessible(user, pk, lock=False):
    # Avoid SELECT FOR UPDATE with DISTINCT on PostgreSQL: authorize first.
    get_object_or_404(visible(user), pk=pk)
    queryset = Mission.objects.select_for_update() if lock else Mission.objects
    return get_object_or_404(queryset, pk=pk)


def member(mission, user):
    return mission.owner_id == user.pk or mission.memberships.filter(user=user).exists()


def notify(mission, actor, recipient, verb):
    if actor.pk != recipient.pk:
        Notification.objects.create(mission=mission, actor=actor, recipient=recipient, verb=verb)


def counts(queryset):
    return queryset.select_related('owner__profile').annotate(
        people_count=Count('memberships', distinct=True),
        contribution_count=Count('contributions', distinct=True),
    ).order_by('-created_at', '-pk')


def state(mission):
    last_entry = mission.contributions.order_by('-updated_at').first()
    last_comment = mission.discussion.order_by('-pk').first()
    return {'people': mission.memberships.count(), 'contributions': mission.contributions.count(),
            'closed': mission.is_closed, 'last_entry': last_entry.updated_at.isoformat() if last_entry else None,
            'last_comment': last_comment.pk if last_comment else None,
            'replies': mission.discussion.count()}


@login_required
@require_GET
def board(request):
    tab = request.GET.get('tab', 'open')
    if tab not in ('open', 'mine', 'invites', 'finished'):
        tab = 'open'
    now = timezone.now()
    queryset = visible(request.user)
    if tab == 'open':
        queryset = queryset.filter(closed_at__isnull=True, ends_at__gt=now)
    elif tab == 'finished':
        queryset = queryset.filter(Q(closed_at__isnull=False) | Q(ends_at__lte=now))
    elif tab == 'mine':
        queryset = queryset.filter(Q(owner=request.user) | Q(memberships__user=request.user))
    else:
        queryset = queryset.filter(invitations__recipient=request.user, invitations__status='pending', closed_at__isnull=True, ends_at__gt=now)
    query = request.GET.get('q', '').strip()[:100]
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(prompt__icontains=query))
    page = Paginator(counts(queryset.distinct()), 9).get_page(request.GET.get('page'))
    for mission in page:
        mission.preview = list(mission.contributions.select_related('author__profile')[:3])
    pending = Invitation.objects.filter(recipient=request.user, status='pending', mission__closed_at__isnull=True, mission__ends_at__gt=now).count()
    return render(request, 'missions/board.html', {'page': page, 'tab': tab, 'query': query, 'pending': pending, 'title': 'Mix Missions'})


@login_required
def create(request):
    ideas = {
        'colour': ('Your city, one colour', 'Pick something green in your city. Share one photo or a few words about what you found. Together, let’s see our everyday places differently.'),
        'day': ('One good thing today', 'Share one small moment that made today a little better. A photo, a thought or a good story — let’s collect the good things.'),
        'weekend': ('Our dream weekend', 'Each person adds one place, activity or idea for a weekend we would love. Let’s turn everyone’s ideas into one shared adventure.'),
    }
    title, prompt = ideas.get(request.GET.get('idea'), ('', ''))
    form = MissionForm(request.POST if request.method == 'POST' else None, request.FILES or None,
                       initial={'title': title, 'prompt': prompt, 'ends_at': timezone.localtime(timezone.now() + timedelta(days=3)).replace(second=0, microsecond=0)})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            mission = form.save(commit=False)
            mission.owner = request.user
            mission.save()
            Membership.objects.create(mission=mission, user=request.user)
        messages.success(request, 'Your mission is live. Add your perspective and pass it on.')
        return redirect('missions:detail', pk=mission.pk)
    return render(request, 'missions/form.html', {'form': form, 'creating': True, 'title': 'Start a mission'})


@login_required
@require_GET
def detail(request, pk):
    mission = accessible(request.user, pk)
    entries = Paginator(mission.contributions.select_related('author__profile').annotate(reaction_count=Count('reactions')).order_by('created_at', 'pk'), 12).get_page(request.GET.get('page'))
    reacted = set(Reaction.objects.filter(user=request.user, contribution__in=entries.object_list).values_list('contribution_id', flat=True))
    discussion = Paginator(mission.discussion.select_related('author__profile').order_by('-created_at', '-pk'), 20).get_page(request.GET.get('discussion_page'))
    return render(request, 'missions/detail.html', {
        'mission': mission, 'entries': entries, 'reacted': reacted, 'discussion': discussion,
        'is_member': member(mission, request.user),
        'invitation': mission.invitations.filter(recipient=request.user, status='pending').first(),
        'own_contribution': mission.contributions.filter(author=request.user).first(),
        'members': mission.memberships.select_related('user__profile').order_by('joined_at')[:8],
        'people_count': mission.memberships.count(), 'contribution_count': mission.contributions.count(),
        'invite_form': InviteForm(), 'discussion_form': DiscussionForm(), 'title': mission.title,
        'initial_update': state(mission),
    })


@login_required
@require_POST
@transaction.atomic
def join(request, pk):
    mission = accessible(request.user, pk, lock=True)
    if mission.is_closed:
        return HttpResponseBadRequest('This collection is finished. Explore another open mission.')
    membership, created = Membership.objects.get_or_create(mission=mission, user=request.user)
    mission.invitations.filter(recipient=request.user, status='pending').update(status='accepted')
    if created:
        notify(mission, request.user, mission.owner, 'joined your mission')
    return redirect('missions:detail', pk=pk)


@login_required
@require_POST
@transaction.atomic
def invite(request, pk):
    mission = accessible(request.user, pk, lock=True)
    if not member(mission, request.user):
        raise Http404
    if mission.is_closed:
        return HttpResponseBadRequest('This mission has finished.')
    form = InviteForm(request.POST)
    if form.is_valid():
        person = User.objects.filter(username__iexact=form.cleaned_data['username'], is_active=True).first()
        if person is None:
            form.add_error('username', 'No account has that username. Search People to find someone.')
        elif member(mission, person):
            form.add_error('username', 'They are already part of this mission.')
        else:
            invitation, created = Invitation.objects.get_or_create(mission=mission, recipient=person, defaults={'sender': request.user})
            if created:
                notify(mission, request.user, person, 'invited you to a mission')
                messages.success(request, f'Invitation sent to @{person.username}.')
            else:
                messages.info(request, 'This person has already been invited. Declined invitations are not resent.')
            return redirect('missions:detail', pk=pk)
    return render(request, 'missions/form.html', {'form': form, 'mission': mission, 'title': 'Pass it on'}, status=400)


@login_required
@require_POST
@transaction.atomic
def respond(request, pk):
    mission = accessible(request.user, pk, lock=True)
    invitation = get_object_or_404(Invitation, mission=mission, recipient=request.user, status='pending')
    action = request.POST.get('action')
    if action == 'accept':
        if mission.is_closed:
            return HttpResponseBadRequest('This mission has finished.')
        Membership.objects.get_or_create(mission=mission, user=request.user)
        invitation.status = 'accepted'
        notify(mission, request.user, invitation.sender, 'accepted your mission invitation')
    elif action == 'decline':
        invitation.status = 'declined'
    else:
        return HttpResponseBadRequest('Choose accept or decline.')
    invitation.save(update_fields=['status'])
    return redirect('missions:detail', pk=pk) if action == 'accept' else redirect('missions:board')


@login_required
def contribute(request, pk):
    with transaction.atomic():
        mission = accessible(request.user, pk, lock=True)
        if not member(mission, request.user):
            raise Http404
        if mission.is_closed:
            return HttpResponseBadRequest('The collection is finished and contributions are locked.')
        existing = mission.contributions.filter(author=request.user).first()
        form = ContributionForm(request.POST if request.method == 'POST' else None, request.FILES or None, instance=existing)
        if request.method == 'POST' and form.is_valid():
            entry = form.save(commit=False)
            entry.mission = mission
            entry.author = request.user
            entry.save()
            if existing is None:
                notify(mission, request.user, mission.owner, 'contributed to your mission')
            messages.success(request, 'Your perspective is part of the collection.')
            return redirect('missions:detail', pk=pk)
    return render(request, 'missions/form.html', {'form': form, 'mission': mission, 'title': 'Your contribution', 'contributing': True})


@login_required
@require_POST
@transaction.atomic
def delete_contribution(request, pk):
    mission = accessible(request.user, pk, lock=True)
    if mission.is_closed:
        return HttpResponseBadRequest('This finished collection is locked.')
    get_object_or_404(Contribution, mission=mission, author=request.user).delete()
    return redirect('missions:detail', pk=pk)


@login_required
@require_POST
@transaction.atomic
def close(request, pk):
    mission = get_object_or_404(Mission.objects.select_for_update(), pk=pk, owner=request.user)
    if not mission.is_closed:
        mission.closed_at = timezone.now()
        mission.save(update_fields=['closed_at'])
        for membership in mission.memberships.select_related('user'):
            notify(mission, request.user, membership.user, 'finished your shared mission')
    return redirect('missions:detail', pk=pk)


@login_required
@require_POST
@transaction.atomic
def discuss(request, pk):
    mission = accessible(request.user, pk, lock=True)
    if not member(mission, request.user):
        raise Http404
    form = DiscussionForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.mission = mission
        comment.author = request.user
        comment.save()
        notify(mission, request.user, mission.owner, 'replied in your mission')
        return redirect('missions:detail', pk=pk)
    return render(request, 'missions/form.html', {'form': form, 'mission': mission, 'title': 'Join the conversation'}, status=400)


@login_required
@require_POST
def delete_discussion(request, pk, comment_pk):
    mission = accessible(request.user, pk)
    get_object_or_404(Discussion, mission=mission, pk=comment_pk, author=request.user).delete()
    return redirect('missions:detail', pk=pk)


@login_required
@require_POST
def react(request, pk, contribution_pk):
    mission = accessible(request.user, pk)
    if not member(mission, request.user):
        raise Http404
    entry = get_object_or_404(Contribution, mission=mission, pk=contribution_pk)
    reaction, created = Reaction.objects.get_or_create(contribution=entry, user=request.user)
    if not created:
        reaction.delete()
    return JsonResponse({'active': created, 'count': entry.reactions.count()})


@login_required
@require_GET
def updates(request, pk):
    mission = accessible(request.user, pk)
    response = JsonResponse(state(mission))
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@require_GET
def media(request, pk, kind, item_pk):
    mission = accessible(request.user, pk)
    if kind == 'cover' and item_pk == mission.pk:
        field = mission.cover
    elif kind == 'entry':
        field = get_object_or_404(Contribution, mission=mission, pk=item_pk).image
    else:
        raise Http404
    if not field:
        raise Http404
    try:
        response = FileResponse(field.open('rb'))
    except (FileNotFoundError, OSError):
        raise Http404
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
