"""Centre de notifications in-app."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .inapp_notifications import unread_count_for
from .models import Notification


@login_required
def notifications_list(request):
    qs = Notification.objects.filter(destinataire=request.user).select_related("expedition")
    unread = qs.filter(lu=False).count()
    return render(
        request,
        "transport/notifications_list.html",
        {
            "notifications": qs[:100],
            "unread_count": unread,
        },
    )


@require_POST
@login_required
def notification_mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, destinataire=request.user)
    notif.lu = True
    notif.save(update_fields=["lu"])
    if notif.lien:
        return redirect(notif.lien)
    return redirect("notifications_list")


@require_POST
@login_required
def notifications_mark_all_read(request):
    Notification.objects.filter(destinataire=request.user, lu=False).update(lu=True)
    return redirect("notifications_list")
