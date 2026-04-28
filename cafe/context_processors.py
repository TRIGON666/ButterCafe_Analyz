from .models import Cart


def cart_items_count(request):
    session_key = request.session.session_key
    if not session_key:
        return {'cart_items_count': 0}

    cart = Cart.objects.filter(session_key=session_key).first()
    if cart is None:
        return {'cart_items_count': 0}

    return {
        'cart_items_count': sum(cart.items.values_list('quantity', flat=True))
    }
