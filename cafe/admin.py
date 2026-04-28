from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Sum, F, DecimalField, Count
from .models import Category, Product, Cart, CartItem, Order, OrderItem, UserProfile, EventLog


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'products_count')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(products_total=Count('products'))

    def products_count(self, obj):
        return format_html('<span class="admin-count-badge">{} тов.</span>', obj.products_total)

    products_count.short_description = 'Товары'
    products_count.admin_order_field = 'products_total'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price_badge', 'cost_price', 'availability_badge', 'calories', 'proteins', 'fats', 'carbs', 'created', 'updated')
    list_filter = ('available', 'created', 'updated', 'category')
    list_editable = ('cost_price',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')
    date_hierarchy = 'created'
    actions = ('mark_available', 'mark_hidden')

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['analytics_dashboard_url'] = reverse('admin_analytics_dashboard')
        return super().changelist_view(request, extra_context=extra_context)

    def price_badge(self, obj):
        return format_html('<span class="admin-money-badge">{} ₽</span>', obj.price)

    price_badge.short_description = 'Цена'
    price_badge.admin_order_field = 'price'

    def availability_badge(self, obj):
        label = 'Доступен' if obj.available else 'Скрыт'
        class_name = 'is-ok' if obj.available else 'is-muted'
        return format_html('<span class="admin-status-badge {}">{}</span>', class_name, label)

    availability_badge.short_description = 'Статус'
    availability_badge.admin_order_field = 'available'


    @admin.action(description='Показать выбранные товары на сайте')
    def mark_available(self, request, queryset):
        updated = queryset.update(available=True)
        self.message_user(request, f'{updated} товар(ов) теперь доступны на сайте.')

    @admin.action(description='Скрыть выбранные товары с сайта')
    def mark_hidden(self, request, queryset):
        updated = queryset.update(available=False)
        self.message_user(request, f'{updated} товар(ов) скрыты с сайта.')


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ('product', 'quantity', 'line_total')
    readonly_fields = ('line_total',)

    def line_total(self, obj):
        if not obj.pk:
            return '—'
        return format_html('<span class="admin-money-badge">{} ₽</span>', obj.total_price)

    line_total.short_description = 'Сумма'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('session_short', 'items_count', 'cart_total', 'created', 'updated')
    search_fields = ('session_key',)
    list_filter = ('created', 'updated')
    inlines = [CartItemInline]
    readonly_fields = ('created', 'updated')
    date_hierarchy = 'updated'
    actions = ('delete_empty_carts',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            items_total=Sum('items__quantity'),
            money_total=Sum(
                F('items__quantity') * F('items__product__price'),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )

    def session_short(self, obj):
        return format_html('<span class="admin-code-badge">{}</span>', obj.session_key[:12])

    session_short.short_description = 'Сессия'
    session_short.admin_order_field = 'session_key'

    def items_count(self, obj):
        return format_html('<span class="admin-count-badge">{} поз.</span>', obj.items_total or 0)

    items_count.short_description = 'Состав'
    items_count.admin_order_field = 'items_total'

    def cart_total(self, obj):
        return format_html('<span class="admin-money-badge">{} ₽</span>', obj.money_total or 0)

    cart_total.short_description = 'Сумма'
    cart_total.admin_order_field = 'money_total'


    @admin.action(description='Удалить пустые выбранные корзины')
    def delete_empty_carts(self, request, queryset):
        empty_carts = queryset.annotate(items_number=Count('items')).filter(items_number=0)
        deleted, _ = empty_carts.delete()
        self.message_user(request, f'Удалено пустых корзин: {deleted}.')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product', 'quantity', 'price', 'line_total')
    readonly_fields = ('line_total',)

    def line_total(self, obj):
        if not obj.pk:
            return '—'
        return format_html('<span class="admin-money-badge">{} ₽</span>', obj.quantity * obj.price)

    line_total.short_description = 'Сумма'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_badge', 'status_badge', 'customer_summary', 'contact_summary', 'delivery_badge', 'total_badge', 'created_short', 'receipt_summary')
    list_filter = ('status', 'delivery_type', 'created_at')
    search_fields = ('name', 'phone', 'email', 'address', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'total', 'delivery_price', 'items_price', 'receipt_text')
    actions = ('mark_confirmed', 'mark_cooking', 'mark_ready', 'mark_delivered', 'mark_cancelled')
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('status', 'user', 'name', 'phone', 'email', 'delivery_type', 'address', 'created_at', 'total', 'delivery_price', 'items_price')
        }),
        ('Детали заказа', {
            'fields': ('need_cutlery', 'need_call', 'comment', 'time')
        }),
        ('Чек', {
            'fields': ('receipt_text',)
        })
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['analytics_dashboard_url'] = reverse('admin_analytics_dashboard')
        return super().changelist_view(request, extra_context=extra_context)

    def order_badge(self, obj):
        return format_html('<span class="admin-order-badge">#{}</span>', obj.id)

    order_badge.short_description = 'Заказ'
    order_badge.admin_order_field = 'id'

    def status_badge(self, obj):
        return format_html(
            '<span class="admin-status-badge status-{}">{}</span>',
            obj.status,
            obj.get_status_display(),
        )

    status_badge.short_description = 'Статус'
    status_badge.admin_order_field = 'status'

    def customer_summary(self, obj):
        username = obj.user.username if obj.user else 'Гость'
        return format_html(
            '<div class="admin-cell-main">{}</div><div class="admin-cell-sub">{}</div>',
            obj.name,
            username,
        )

    customer_summary.short_description = 'Клиент'
    customer_summary.admin_order_field = 'name'

    def contact_summary(self, obj):
        return format_html(
            '<div class="admin-cell-main">{}</div><div class="admin-cell-sub">{}</div>',
            obj.phone or '—',
            obj.email or 'без email',
        )

    contact_summary.short_description = 'Контакты'

    def delivery_badge(self, obj):
        class_name = 'is-delivery' if obj.delivery_type == 'delivery' else 'is-pickup'
        return format_html('<span class="admin-status-badge {}">{}</span>', class_name, obj.get_delivery_type_display())

    delivery_badge.short_description = 'Получение'
    delivery_badge.admin_order_field = 'delivery_type'

    def total_badge(self, obj):
        return format_html('<span class="admin-money-badge">{} ₽</span>', obj.total)

    total_badge.short_description = 'Сумма'
    total_badge.admin_order_field = 'total'

    def created_short(self, obj):
        return format_html(
            '<div class="admin-cell-main">{}</div><div class="admin-cell-sub">{}</div>',
            obj.created_at.strftime('%d.%m.%Y'),
            obj.created_at.strftime('%H:%M'),
        )

    created_short.short_description = 'Дата'
    created_short.admin_order_field = 'created_at'

    def receipt_summary(self, obj):
        text = obj.receipt_text or obj.comment or ''
        short = text[:110] + '...' if len(text) > 110 else text
        return format_html('<div class="admin-receipt-preview">{}</div>', short or '—')

    receipt_summary.short_description = 'Чек'

    def _set_status(self, request, queryset, status, label):
        updated = queryset.update(status=status)
        self.message_user(request, f'{updated} заказ(ов) переведено в статус "{label}".')

    @admin.action(description='Статус: подтвержден')
    def mark_confirmed(self, request, queryset):
        self._set_status(request, queryset, 'confirmed', 'Подтвержден')

    @admin.action(description='Статус: готовится')
    def mark_cooking(self, request, queryset):
        self._set_status(request, queryset, 'cooking', 'Готовится')

    @admin.action(description='Статус: готов')
    def mark_ready(self, request, queryset):
        self._set_status(request, queryset, 'ready', 'Готов')

    @admin.action(description='Статус: доставлен')
    def mark_delivered(self, request, queryset):
        self._set_status(request, queryset, 'delivered', 'Доставлен')

    @admin.action(description='Статус: отменен')
    def mark_cancelled(self, request, queryset):
        self._set_status(request, queryset, 'cancelled', 'Отменен')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'default_address')
    search_fields = ('user__username', 'user__email', 'phone', 'default_address')


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'event_type', 'user', 'dashboard_link')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('timestamp', 'event_type', 'user', 'metadata_json')

    def dashboard_link(self, obj):
        return format_html('<a href="{}">Открыть диаграммы</a>', reverse('admin_analytics_dashboard'))

    dashboard_link.short_description = 'Диаграммы'
