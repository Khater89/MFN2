from django.conf import settings
def global_context(request):
    profile = getattr(request.user, 'profile', None) if request.user.is_authenticated else None
    return {'my_profile': profile, 'marketplace_timezone': settings.TIME_ZONE}
