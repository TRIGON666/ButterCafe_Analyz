import csv
import json
from datetime import datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from cafe.models import EventLog, Order


class Command(BaseCommand):
    help = 'Exports previous-day orders and events into data_lake/YYYY/MM/DD'

    def handle(self, *args, **options):
        local_today = timezone.localdate()
        export_day = local_today - timedelta(days=1)

        day_start = timezone.make_aware(datetime.combine(export_day, time.min))
        day_end = timezone.make_aware(datetime.combine(export_day, time.max))

        base_dir = Path(settings.BASE_DIR) / 'data_lake' / export_day.strftime('%Y') / export_day.strftime('%m') / export_day.strftime('%d')
        base_dir.mkdir(parents=True, exist_ok=True)

        orders = list(
            Order.objects.filter(created_at__gte=day_start, created_at__lte=day_end)
            .select_related('user')
            .prefetch_related('items__product')
            .order_by('created_at')
        )
        events = list(
            EventLog.objects.filter(timestamp__gte=day_start, timestamp__lte=day_end)
            .select_related('user')
            .order_by('timestamp')
        )

        self._export_orders_csv(base_dir / 'orders.csv', orders)
        self._export_orders_json(base_dir / 'orders.json', orders)
        self._export_events_csv(base_dir / 'events.csv', events)

        self.stdout.write(
            self.style.SUCCESS(
                f'Export completed: {len(orders)} orders and {len(events)} events to {base_dir}'
            )
        )

    def _export_orders_csv(self, file_path, orders):
        with file_path.open('w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([
                'id', 'created_at', 'user_id', 'username', 'name', 'phone', 'email',
                'address', 'delivery_type', 'need_cutlery', 'need_call', 'comment',
                'time', 'items_price', 'delivery_price', 'total', 'items'
            ])
            for order in orders:
                items_repr = '; '.join(
                    f'{item.product_id}:{item.product.name} x{item.quantity} @ {item.price}'
                    for item in order.items.all()
                )
                writer.writerow([
                    order.id,
                    timezone.localtime(order.created_at).isoformat(),
                    order.user_id or '',
                    order.user.username if order.user else '',
                    order.name,
                    order.phone,
                    order.email,
                    order.address,
                    order.delivery_type,
                    order.need_cutlery,
                    order.need_call,
                    order.comment,
                    order.time,
                    order.items_price,
                    order.delivery_price,
                    order.total,
                    items_repr,
                ])

    def _export_orders_json(self, file_path, orders):
        payload = []
        for order in orders:
            payload.append({
                'id': order.id,
                'created_at': timezone.localtime(order.created_at).isoformat(),
                'user_id': order.user_id,
                'username': order.user.username if order.user else None,
                'name': order.name,
                'phone': order.phone,
                'email': order.email,
                'address': order.address,
                'delivery_type': order.delivery_type,
                'need_cutlery': order.need_cutlery,
                'need_call': order.need_call,
                'comment': order.comment,
                'time': order.time,
                'items_price': float(order.items_price),
                'delivery_price': float(order.delivery_price),
                'total': float(order.total),
                'items': [
                    {
                        'product_id': item.product_id,
                        'product_name': item.product.name,
                        'quantity': item.quantity,
                        'price': float(item.price),
                    }
                    for item in order.items.all()
                ],
            })

        with file_path.open('w', encoding='utf-8') as json_file:
            json.dump(payload, json_file, ensure_ascii=False, indent=2)

    def _export_events_csv(self, file_path, events):
        with file_path.open('w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(['timestamp', 'user_id', 'username', 'event_type', 'metadata_json'])
            for event in events:
                writer.writerow([
                    timezone.localtime(event.timestamp).isoformat(),
                    event.user_id or '',
                    event.user.username if event.user else '',
                    event.event_type,
                    json.dumps(event.metadata_json, ensure_ascii=False),
                ])
