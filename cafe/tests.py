from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from cafe.models import Category, EventLog, Order, OrderItem, Product


class AnalyticsCommandsTest(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='report_user', password='Pass12345!', email='u@test.local')
		self.category = Category.objects.create(name='Test category', slug='test-category')
		self.product = Product.objects.create(
			category=self.category,
			name='Test product',
			slug='test-product',
			description='Test',
			price=Decimal('200.00'),
			cost_price=Decimal('120.00'),
			image='products/test.jpg',
			available=True,
		)

		self.order = Order.objects.create(
			user=self.user,
			name='Test User',
			phone='+70000000000',
			email='u@test.local',
			delivery_type='pickup_10a',
			total=Decimal('200.00'),
			delivery_price=Decimal('0.00'),
			items_price=Decimal('200.00'),
		)
		OrderItem.objects.create(order=self.order, product=self.product, quantity=1, price=Decimal('200.00'))

		self.event = EventLog.objects.create(
			user=self.user,
			event_type='order_created',
			metadata_json={'order_id': self.order.id},
		)

		target_day = timezone.localdate() - timedelta(days=1)
		target_dt = timezone.make_aware(datetime.combine(target_day, time(hour=12)))
		Order.objects.filter(id=self.order.id).update(created_at=target_dt)
		EventLog.objects.filter(id=self.event.id).update(timestamp=target_dt)

	def test_export_daily_analytics_prepares_expected_files(self):
		expected_dir = Path(settings.BASE_DIR) / 'data_lake' / '2026' / '04' / '21'
		with (
			patch('django.utils.timezone.localdate', return_value=date(2026, 4, 22)),
			patch('cafe.management.commands.export_daily_analytics.Command._export_orders_csv') as orders_csv,
			patch('cafe.management.commands.export_daily_analytics.Command._export_orders_json') as orders_json,
			patch('cafe.management.commands.export_daily_analytics.Command._export_events_csv') as events_csv,
		):
			call_command('export_daily_analytics')

		orders_csv.assert_called_once()
		orders_json.assert_called_once()
		events_csv.assert_called_once()
		self.assertEqual(orders_csv.call_args.args[0], expected_dir / 'orders.csv')
		self.assertEqual(orders_json.call_args.args[0], expected_dir / 'orders.json')
		self.assertEqual(events_csv.call_args.args[0], expected_dir / 'events.csv')

	@override_settings(
		EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
		OWNER_REPORT_EMAIL='owner@test.local',
		DEFAULT_FROM_EMAIL='report@test.local',
		METABASE_USERNAME='',
		METABASE_PASSWORD='',
	)
	def test_generate_daily_report_sends_email(self):
		call_command('generate_daily_report')

		self.assertEqual(len(mail.outbox), 1)
		sent = mail.outbox[0]
		self.assertIn('Ежедневный отчет ButterCafe', sent.body)
		self.assertIn('Источник метрик: local-db', sent.body)
		self.assertIn('owner@test.local', sent.to)


class CartOrderSecurityTest(TestCase):
	def setUp(self):
		self.category = Category.objects.create(name='Bakery', slug='bakery')
		self.product = Product.objects.create(
			category=self.category,
			name='Croissant',
			slug='croissant',
			description='Fresh',
			price=Decimal('120.00'),
			cost_price=Decimal('70.00'),
			image='products/croissant.jpg',
			available=True,
		)

	def test_get_requests_for_cart_mutations_are_not_allowed(self):
		resp_add = self.client.get(f'/cart/add/{self.product.id}/')
		self.assertEqual(resp_add.status_code, 405)

		self.client.post(f'/cart/add/{self.product.id}/')
		resp_remove = self.client.get('/cart/remove/1/')
		self.assertEqual(resp_remove.status_code, 405)

	def test_empty_order_returns_400(self):
		response = self.client.post('/order/create/', data={})
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json().get('success'), False)
