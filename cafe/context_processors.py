from .models import Cart


def cart_items_count(request):
    if not request.session.session_key:
        request.session.create()
    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return {
        'cart_items_count': sum(item.quantity for item in cart.items.all())
    }
