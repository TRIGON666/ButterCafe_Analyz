import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any
from urllib import error, parse, request

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, F, Sum
from django.utils import timezone

from cafe.models import Order, OrderItem


@dataclass
class DailyMetrics:
    report_date: str
    revenue: Decimal
    orders_count: int
    avg_check: Decimal
    new_clients: int
    top_products: list[dict[str, Any]]
    source: str


def previous_day_bounds():
    target_day = timezone.localdate() - timedelta(days=1)
    start_dt = timezone.make_aware(datetime.combine(target_day, time.min))
    end_dt = timezone.make_aware(datetime.combine(target_day, time.max))
    return target_day, start_dt, end_dt


def local_metrics(start_dt, end_dt):
    orders = Order.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
    totals = orders.aggregate(
        revenue=Sum('total'),
        orders_count=Count('id'),
    )
    revenue = totals['revenue'] or Decimal('0')
    orders_count = totals['orders_count'] or 0
    avg_check = (revenue / orders_count) if orders_count else Decimal('0')

    new_clients = User.objects.filter(date_joined__gte=start_dt, date_joined__lte=end_dt).count()

    top_products = list(
        OrderItem.objects.filter(order__created_at__gte=start_dt, order__created_at__lte=end_dt)
        .values(product_name=F('product__name'))
        .annotate(quantity=Sum('quantity'))
        .order_by('-quantity', 'product_name')[:3]
    )

    return {
        'revenue': revenue,
        'orders_count': orders_count,
        'avg_check': avg_check,
        'new_clients': new_clients,
        'top_products': top_products,
    }


def _post_json(url, payload, headers=None):
    data = json.dumps(payload).encode('utf-8')
    req_headers = {'Content-Type': 'application/json'}
    if headers:
        req_headers.update(headers)
    req = request.Request(url, data=data, headers=req_headers, method='POST')
    with request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _extract_first_number(payload):
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            for value in first.values():
                if isinstance(value, (int, float)):
                    return Decimal(str(value))
        if isinstance(first, (int, float)):
            return Decimal(str(first))
    return Decimal('0')


def _extract_top_products(payload):
    if not isinstance(payload, list):
        return []
    result = []
    for row in payload[:3]:
        if isinstance(row, dict):
            keys = list(row.keys())
            if len(keys) >= 2:
                result.append({'product_name': str(row[keys[0]]), 'quantity': int(row[keys[1]] or 0)})
    return result


def metabase_metrics():
    username = settings.METABASE_USERNAME
    password = settings.METABASE_PASSWORD
    if not username or not password:
        raise RuntimeError('METABASE credentials are not configured')

    base_url = settings.METABASE_URL.rstrip('/')
    session = _post_json(f'{base_url}/api/session', {'username': username, 'password': password})
    token = session.get('id')
    if not token:
        raise RuntimeError('Unable to obtain Metabase session token')

    headers = {'X-Metabase-Session': token}

    card_map = {
        'revenue': settings.METABASE_REVENUE_CARD_ID,
        'orders_count': settings.METABASE_ORDERS_CARD_ID,
        'avg_check': settings.METABASE_AVG_CHECK_CARD_ID,
        'new_clients': settings.METABASE_NEW_CLIENTS_CARD_ID,
        'top_products': settings.METABASE_TOP_PRODUCTS_CARD_ID,
    }

    metrics = {
        'revenue': Decimal('0'),
        'orders_count': 0,
        'avg_check': Decimal('0'),
        'new_clients': 0,
        'top_products': [],
    }

    for key, card_id in card_map.items():
        if not card_id:
            continue
        payload = _post_json(f'{base_url}/api/card/{card_id}/query/json', {'parameters': []}, headers=headers)
        if key == 'top_products':
            metrics[key] = _extract_top_products(payload)
        else:
            value = _extract_first_number(payload)
            if key in ('orders_count', 'new_clients'):
                metrics[key] = int(value)
            else:
                metrics[key] = value

    return metrics


def get_daily_metrics():
    report_day, start_dt, end_dt = previous_day_bounds()

    try:
        metrics = metabase_metrics()
        source = 'metabase'
    except (RuntimeError, error.URLError, error.HTTPError, ValueError, TimeoutError):
        metrics = local_metrics(start_dt, end_dt)
        source = 'local-db'

    return DailyMetrics(
        report_date=report_day.strftime('%d.%m.%Y'),
        revenue=metrics['revenue'],
        orders_count=metrics['orders_count'],
        avg_check=metrics['avg_check'],
        new_clients=metrics['new_clients'],
        top_products=metrics['top_products'],
        source=source,
    )


def render_daily_report_text(daily_metrics):
    if daily_metrics.top_products:
        top = ', '.join(f"{item['product_name']} ({item['quantity']})" for item in daily_metrics.top_products)
    else:
        top = 'Нет данных'

    return (
        f"Ежедневный отчет ButterCafe за {daily_metrics.report_date}\n"
        f"Источник метрик: {daily_metrics.source}\n\n"
        f"Выручка за день: {daily_metrics.revenue:.2f} руб.\n"
        f"Количество заказов: {daily_metrics.orders_count}\n"
        f"Средний чек: {daily_metrics.avg_check:.2f} руб.\n"
        f"Новых клиентов: {daily_metrics.new_clients}\n"
        f"Топ-3 товара: {top}\n"
    )
