from allauth.account.signals import user_signed_up
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import EventLog


def _request_metadata(request):
    if request is None:
        return {}
    return {
        'ip': request.META.get('REMOTE_ADDR', ''),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
    }


@receiver(user_signed_up)
def on_user_signed_up(request, user, **kwargs):
    EventLog.objects.create(
        event_type='user_registered',
        user=user,
        metadata_json=_request_metadata(request),
    )


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    EventLog.objects.create(
        event_type='user_logged_in',
        user=user,
        metadata_json=_request_metadata(request),
    )
