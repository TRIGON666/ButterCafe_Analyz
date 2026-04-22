from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Category, Product, Cart, CartItem, Order, UserProfile, EventLog


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'cost_price', 'available', 'calories', 'proteins', 'fats', 'carbs', 'created', 'updated')
    list_filter = ('available', 'created', 'updated', 'category')
    list_editable = ('price', 'cost_price', 'available')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')
    date_hierarchy = 'created'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['analytics_dashboard_url'] = reverse('admin_analytics_dashboard')
        return super().changelist_view(request, extra_context=extra_context)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'created', 'updated')
    inlines = [CartItemInline]
    readonly_fields = ('created', 'updated')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'phone', 'delivery_type', 'total', 'created_at', 'receipt_text')
    list_filter = ('delivery_type', 'created_at')
    search_fields = ('name', 'phone', 'email', 'address', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'total', 'delivery_price', 'items_price', 'receipt_text')
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('user', 'name', 'phone', 'email', 'delivery_type', 'address', 'created_at', 'total', 'delivery_price', 'items_price')
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
