from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название категории')
    slug = models.SlugField(unique=True, verbose_name='URL')
    description = models.TextField(blank=True, verbose_name='Описание')
    image = models.ImageField(upload_to='categories/', blank=True, verbose_name='Изображение')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', verbose_name='Категория')
    name = models.CharField(max_length=200, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='URL')
    description = models.TextField(verbose_name='Описание')
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='Цена')
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], verbose_name='Себестоимость')
    image = models.ImageField(upload_to='products/', verbose_name='Изображение')
    available = models.BooleanField(default=True, verbose_name='Доступен')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    calories = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, verbose_name='Калорийность (ккал)')
    proteins = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, verbose_name='Белки (г)')
    fats = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, verbose_name='Жиры (г)')
    carbs = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, verbose_name='Углеводы (г)')

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.cost_price is not None and self.price is not None and self.cost_price > self.price:
            raise ValidationError({'cost_price': 'Себестоимость не может быть больше цены.'})

class Cart(models.Model):
    session_key = models.CharField(max_length=40, unique=True, verbose_name='Ключ сессии')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    def __str__(self):
        return f'Корзина {self.session_key}'

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name='Корзина')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name='Количество')

    class Meta:
        verbose_name = 'Товар в корзине'
        verbose_name_plural = 'Товары в корзине'
        unique_together = ('cart', 'product')

    def __str__(self):
        return f'{self.quantity} x {self.product.name}'

    @property
    def total_price(self):
        return self.quantity * self.product.price


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name='Пользователь')
    phone = models.CharField(max_length=30, blank=True, verbose_name='Телефон')
    default_address = models.CharField(max_length=255, blank=True, verbose_name='Адрес по умолчанию')
    favorite_products = models.ManyToManyField(Product, blank=True, related_name='favorited_by', verbose_name='Любимые товары')

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f'Профиль {self.user.username}'

class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('confirmed', 'Подтвержден'),
        ('cooking', 'Готовится'),
        ('ready', 'Готов'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменен'),
    ]

    DELIVERY_CHOICES = [
        ('pickup_10a', 'Самовывоз с Лобачевского 10а'),
        ('pickup_43', 'Самовывоз с Щапова 43'),
        ('pickup_51', 'Самовывоз с Сибгата Хакима 51 (ЖК Столичный)'),
        ('pickup_20a', 'Самовывоз с Чистопольской 20а'),
        ('delivery', 'Доставка'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name='Пользователь')
    name = models.CharField(max_length=100, verbose_name='Имя')
    phone = models.CharField(max_length=30, verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Email')
    address = models.CharField(max_length=255, blank=True, verbose_name='Адрес')
    delivery_type = models.CharField(max_length=32, choices=DELIVERY_CHOICES, verbose_name='Способ получения')
    need_cutlery = models.BooleanField(default=True, verbose_name='Одноразовые приборы')
    need_call = models.BooleanField(default=True, verbose_name='Звонок для подтверждения')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    time = models.CharField(max_length=20, blank=True, verbose_name='Время к заказу')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус заказа')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата заказа')
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма заказа')
    delivery_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Стоимость доставки')
    items_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Стоимость товаров')
    receipt_text = models.TextField(blank=True, verbose_name='Чек (текст)')

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ #{self.id} от {self.name}'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='Товар')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена за единицу')

    class Meta:
        verbose_name = 'Товар в заказе'
        verbose_name_plural = 'Товары в заказе'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'


class EventLog(models.Model):
    EVENT_TYPE_CHOICES = [
        ('user_registered', 'Регистрация пользователя'),
        ('user_logged_in', 'Вход пользователя'),
        ('added_to_cart', 'Добавление в корзину'),
        ('order_created', 'Оформление заказа'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время события')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='event_logs', verbose_name='Пользователь')
    event_type = models.CharField(max_length=64, choices=EVENT_TYPE_CHOICES, verbose_name='Тип события')
    metadata_json = models.JSONField(default=dict, blank=True, verbose_name='Метаданные')

    class Meta:
        verbose_name = 'Событие'
        verbose_name_plural = 'События'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.event_type} ({self.timestamp:%Y-%m-%d %H:%M:%S})'
