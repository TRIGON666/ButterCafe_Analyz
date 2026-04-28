from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.db import transaction
import logging
from django.db.models import Q, Sum
from .forms import OrderCreateForm
from .models import Category, Product, Cart, CartItem, Order, OrderItem, UserProfile, EventLog
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

def get_cart(request):
    if not request.session.session_key:
        request.session.create()
    cart, created = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart

def get_cart_items_count(request):
    session_key = request.session.session_key
    if not session_key:
        return 0

    return CartItem.objects.filter(cart__session_key=session_key).aggregate(
        total=Sum('quantity')
    )['total'] or 0


def get_cart_queryset(cart):
    return cart.items.select_related('product', 'product__category')


def get_delivery_price(delivery_type, has_items=True):
    if not has_items or delivery_type != 'delivery':
        return 0
    return 100


def get_or_create_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def log_event(event_type, user=None, metadata=None):
    EventLog.objects.create(
        event_type=event_type,
        user=user,
        metadata_json=metadata or {}
    )

def home(request):
    categories = Category.objects.all()
    featured_products = Product.objects.filter(available=True).select_related('category')[:6]
    
    favorite_product_ids = []
    if request.user.is_authenticated:
        profile = get_or_create_user_profile(request.user)
        favorite_product_ids = list(profile.favorite_products.values_list('id', flat=True))

    context = {
        'categories': categories,
        'featured_products': featured_products,
        'favorite_product_ids': favorite_product_ids,
        'cart_items_count': get_cart_items_count(request)
    }
    return render(request, 'home.html', context)

def menu(request):
    categories = Category.objects.all()
    products = Product.objects.filter(available=True).select_related('category')
    category_id = request.GET.get('category')
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    search_query = request.GET.get('search')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
        
    favorite_product_ids = []
    if request.user.is_authenticated:
        profile = get_or_create_user_profile(request.user)
        favorite_product_ids = list(profile.favorite_products.values_list('id', flat=True))
    
    context = {
        'categories': categories,
        'products': products,
        'favorite_product_ids': favorite_product_ids,
        'cart_items_count': get_cart_items_count(request)
    }
    return render(request, 'menu.html', context)

def cart(request):
    cart = get_cart(request)
    cart_items = get_cart_queryset(cart)
    total_price = sum(item.total_price for item in cart_items)
    
    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'cart_items_count': sum(item.quantity for item in cart_items)
    }
    return render(request, 'cart.html', context)

@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, available=True)
    cart = get_cart(request)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save(update_fields=['quantity'])

    log_event(
        event_type='added_to_cart',
        user=request.user if request.user.is_authenticated else None,
        metadata={
            'product_id': product.id,
            'cart_session_key': cart.session_key,
            'quantity': cart_item.quantity,
        }
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'cart_items_count': get_cart_items_count(request)})
    messages.success(request, f'Товар "{product.name}" добавлен в корзину')
    return redirect('cafe:cart')

@require_POST
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart=get_cart(request))
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f'Товар "{product_name}" удален из корзины')
    return redirect('cafe:cart')

@require_POST
def update_cart_item(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart=get_cart(request))
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        messages.error(request, 'Некорректное количество товара')
        return redirect('cafe:cart')
    
    if quantity > 0:
        cart_item.quantity = quantity
        cart_item.save(update_fields=['quantity'])
    else:
        cart_item.delete()
    
    return redirect('cafe:cart')

def product_modal(request, product_id):
    product = get_object_or_404(Product, id=product_id, available=True)
    html = render_to_string('product_modal.html', {'product': product, 'cart_items_count': get_cart_items_count(request)}, request=request)
    return JsonResponse({'html': html})

def order_modal(request):
    cart = get_cart(request)
    cart_items = get_cart_queryset(cart)
    items_price = sum(item.total_price for item in cart_items)
    delivery_price = get_delivery_price('pickup_10a', bool(items_price))
    total = items_price + delivery_price

    initial_name = ''
    initial_phone = ''
    initial_email = ''
    initial_address = ''
    if request.user.is_authenticated:
        profile = get_or_create_user_profile(request.user)
        initial_name = request.user.first_name
        initial_phone = profile.phone
        initial_email = request.user.email
        initial_address = profile.default_address

    html = render_to_string('order_modal.html', {
        'cart_items': cart_items,
        'items_price': items_price,
        'delivery_price': delivery_price,
        'total': total,
        'initial_name': initial_name,
        'initial_phone': initial_phone,
        'initial_email': initial_email,
        'initial_address': initial_address,
    }, request=request)
    return JsonResponse({'html': html})

@require_POST
def order_create(request):
    cart = get_cart(request)
    cart_items = list(get_cart_queryset(cart))
    if not cart_items:
        return JsonResponse({'success': False, 'errors': ['Корзина пуста']}, status=400)

    items_price = sum(item.total_price for item in cart_items)
    form = OrderCreateForm(request.POST)
    if not form.is_valid():
        errors = []
        for field_errors in form.errors.values():
            errors.extend(str(error) for error in field_errors)
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    data = form.cleaned_data
    delivery_price = get_delivery_price(data['delivery_type'], bool(cart_items))
    total = items_price + delivery_price
    try:
        # Формируем текст чека
        receipt_lines = [
            f'Заказ от: {data["name"]}\nТелефон: {data["phone"]}\nEmail: {data.get("email", "")}\n',
            f'Способ получения: {dict(Order.DELIVERY_CHOICES).get(data["delivery_type"], "")}\n',
            f'Адрес: {data.get("address", "")}\n',
            'Состав заказа:'
        ]
        for item in cart_items:
            receipt_lines.append(f'- {item.product.name} × {item.quantity} = {item.total_price} р.')
        receipt_lines += [
            f'\nСтоимость товаров: {items_price} р.',
            f'Доставка: {delivery_price} р.',
            f'Итого: {total} р.',
            f'Комментарий: {data.get("comment", "")}\n',
            f'Время к заказу: {data.get("time", "")}\n',
            f'Одноразовые приборы: {"Да" if data["need_cutlery"] else "Нет"}',
            f'Звонок для подтверждения: {"Да" if data["need_call"] else "Нет"}',
        ]
        receipt_text = '\n'.join(receipt_lines)
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=data['name'],
                phone=data['phone'],
                email=data.get('email', ''),
                address=data.get('address', ''),
                delivery_type=data['delivery_type'],
                need_cutlery=data['need_cutlery'],
                need_call=data['need_call'],
                comment=data.get('comment', ''),
                time=data.get('time', ''),
                total=total,
                delivery_price=delivery_price,
                items_price=items_price,
                receipt_text=receipt_text
            )

            log_event(
                event_type='order_created',
                user=request.user if request.user.is_authenticated else None,
                metadata={
                    'order_id': order.id,
                    'delivery_type': order.delivery_type,
                    'items_price': float(order.items_price),
                    'delivery_price': float(order.delivery_price),
                    'total': float(order.total),
                    'items_count': sum(item.quantity for item in cart_items),
                }
            )

            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                for item in cart_items
            ])

            if request.user.is_authenticated:
                profile = get_or_create_user_profile(request.user)
                profile.phone = data['phone']
                if data.get('address'):
                    profile.default_address = data['address']
                profile.save(update_fields=['phone', 'default_address'])

            cart.items.all().delete()
            return JsonResponse({'success': True})
    except Exception as e:
        logging.error("Failed to create order", exc_info=True)
        return JsonResponse({'success': False, 'errors': ['Не удалось оформить заказ. Попробуйте позже.']}, status=500)

def about(request):
    context = {
        'cart_items_count': get_cart_items_count(request)
    }
    return render(request, 'about.html', context)

def addresses(request):
    return render(request, 'addresses.html', {
        'cart_items_count': get_cart_items_count(request)
    })


@login_required
def toggle_favorite(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        profile = get_or_create_user_profile(request.user)
        
        if product in profile.favorite_products.all():
            profile.favorite_products.remove(product)
            is_favorite = False
        else:
            profile.favorite_products.add(product)
            is_favorite = True
            
        return JsonResponse({'success': True, 'is_favorite': is_favorite})
    return JsonResponse({'success': False}, status=400)

@login_required
def favorites(request):
    profile = get_or_create_user_profile(request.user)
    fav_products = profile.favorite_products.filter(available=True)
    return render(request, 'favorites.html', {
        'products': fav_products,
        'cart_items_count': get_cart_items_count(request)
    })

@login_required
def profile(request):
    profile_obj = get_or_create_user_profile(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Handle admin actions
        if request.user.is_staff and action:
            try:
                if action == 'export_daily_analytics':
                    call_command('export_daily_analytics')
                    messages.success(request, 'Экспорт аналитики выполнен')
                elif action == 'generate_daily_report':
                    call_command('generate_daily_report')
                    messages.success(request, 'Команда отправки отчета выполнена')
                else:
                    messages.warning(request, 'Неизвестное действие')
            except Exception as exc:
                messages.error(request, f'Ошибка выполнения: {exc}')
            return redirect('cafe:profile')

        # Regular profile update
        request.user.first_name = request.POST.get('name', '').strip()
        request.user.email = request.POST.get('email', '').strip()
        request.user.save(update_fields=['first_name', 'email'])

        profile_obj.phone = request.POST.get('phone', '').strip()
        profile_obj.default_address = request.POST.get('default_address', '').strip()
        profile_obj.save(update_fields=['phone', 'default_address'])

        messages.success(request, 'Профиль обновлен')
        return redirect('cafe:profile')

    context = {
        'profile_obj': profile_obj,
        'cart_items_count': get_cart_items_count(request)
    }
    return render(request, 'profile.html', context)





@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items__product')
    context = {
        'orders': orders,
        'cart_items_count': get_cart_items_count(request)
    }
    return render(request, 'order_history.html', context)


@login_required
@require_POST
def repeat_order(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), id=order_id, user=request.user)
    cart = get_cart(request)

    for order_item in order.items.all():
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=order_item.product,
            defaults={'quantity': order_item.quantity}
        )
        if not created:
            cart_item.quantity += order_item.quantity
            cart_item.save()

    messages.success(request, f'Товары из заказа #{order.id} добавлены в корзину')
    return redirect('cafe:cart')
