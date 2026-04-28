from django.db.models import Sum

from .models import CartItem


def cart_items_count(request):
    session_key = request.session.session_key
    if not session_key:
        return {'cart_items_count': 0}

    return {
        'cart_items_count': CartItem.objects.filter(cart__session_key=session_key).aggregate(
            total=Sum('quantity')
        )['total'] or 0
    }
