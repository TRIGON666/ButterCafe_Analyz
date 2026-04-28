from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from smtplib import SMTPException
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from cafe.models import Category, EventLog, Order, OrderItem, Product
from cafe.services.reporting import DailyMetrics, render_daily_report_html


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
		expected_dir = Path(settings.ANALYTICS_EXPORT_ROOT) / '2026' / '04' / '21'
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

	@override_settings(
		EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
		OWNER_REPORT_EMAIL='owner@test.local',
		DEFAULT_FROM_EMAIL='report@test.local',
		METABASE_USERNAME='',
		METABASE_PASSWORD='',
	)
	def test_generate_daily_report_saves_local_copy_when_email_fails(self):
		with TemporaryDirectory() as tmp_dir, override_settings(ANALYTICS_EXPORT_ROOT=tmp_dir):
			with patch(
				'cafe.management.commands.generate_daily_report.EmailMultiAlternatives.send',
				side_effect=SMTPException('smtp unavailable'),
			):
				output = StringIO()
				call_command('generate_daily_report', stdout=output)

			self.assertIn('Report was not sent', output.getvalue())
			report_files = list(Path(tmp_dir).glob('reports/*/*/*/daily_report.txt'))
			self.assertEqual(len(report_files), 1)
			self.assertIn('Ежедневный отчет ButterCafe', report_files[0].read_text(encoding='utf-8'))

	def test_daily_report_html_escapes_dynamic_values(self):
		metrics = DailyMetrics(
			report_date='28.04.2026',
			revenue=Decimal('100.00'),
			orders_count=1,
			avg_check=Decimal('100.00'),
			new_clients=0,
			top_products=[{'product_name': '<script>alert(1)</script>', 'quantity': 1}],
			recommendations=['<b>Проверить витрину</b>'],
			source='local-db',
		)

		html = render_daily_report_html(metrics)

		self.assertNotIn('<script>alert(1)</script>', html)
		self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
		self.assertNotIn('<b>Проверить витрину</b>', html)
		self.assertIn('&lt;b&gt;Проверить витрину&lt;/b&gt;', html)


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

	def test_order_create_returns_success_page_for_guest(self):
		self.client.post(f'/cart/add/{self.product.id}/')

		response = self.client.post(
			'/order/create/',
			data={
				'name': 'Guest',
				'phone': '+70000000000',
				'delivery_type': 'pickup_10a',
			},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload.get('success'), True)
		self.assertIn('order_url', payload)

		order = Order.objects.get(id=payload['order_id'])
		self.assertEqual(order.items.count(), 1)

		event = EventLog.objects.get(event_type='order_created', metadata_json__order_id=order.id)
		self.assertEqual(event.metadata_json.get('cart_session_key'), self.client.session.session_key)

		success_response = self.client.get(payload['order_url'])
		self.assertEqual(success_response.status_code, 200)
		self.assertContains(success_response, f'Заказ #{order.id}')
		self.assertIn(order.id, self.client.session.get('recent_order_ids'))


class MetabaseEmbedTest(TestCase):
	@override_settings(
		METABASE_URL='http://metabase.test',
		METABASE_DASHBOARD_ID='7',
		METABASE_EMBED_SECRET='test-secret',
		METABASE_EMBED_THEME='light',
	)
	def test_dashboard_embed_url_uses_signed_token(self):
		from cafe.services.metabase import build_dashboard_embed_url

		url = build_dashboard_embed_url()

		self.assertTrue(url.startswith('http://metabase.test/embed/dashboard/'))
		self.assertIn('#bordered=true&titled=true&theme=light', url)
		token = url.split('/embed/dashboard/', 1)[1].split('#', 1)[0]
		self.assertEqual(len(token.split('.')), 3)
