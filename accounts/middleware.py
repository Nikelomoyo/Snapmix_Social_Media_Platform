import time
from django.core.cache import cache
from django.http import HttpResponse
def limited(key, limit, seconds=60):
    key = f'rate:{key}:{int(time.time() // seconds)}'
    cache.add(key, 0, seconds + 1)
    return cache.incr(key) > limit
class RateLimitMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        if request.method == 'POST':
            auth = request.path in ['/login/', '/signup/']
            key = request.META.get('REMOTE_ADDR', '') if auth else str(request.user.pk)
            if limited(f'{"auth" if auth else "write"}:{key}', 15 if auth else 60):
                return HttpResponse('Too many requests. Try again in a minute.', status=429)
        return self.get_response(request)
