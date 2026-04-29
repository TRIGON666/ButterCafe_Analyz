import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib import error, request

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, F, Sum
from django.utils.html import escape
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
    recommendations: list[str]
    source: str


def previous_day_bounds():
    target_day = timezone.localdate() - timedelta(days=1)
    start_dt = timezone.make_aware(datetime.combine(target_day, time.min))
    end_dt = timezone.make_aware(datetime.combine(target_day, time.max))
    return target_day, start_dt, end_dt


def local_metrics(start_dt, end_dt):
    orders = Order.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt).exclude(status='cancelled')
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
        .exclude(order__status='cancelled')
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

    recommendations = build_daily_recommendations(metrics)

    return DailyMetrics(
        report_date=report_day.strftime('%d.%m.%Y'),
        revenue=metrics['revenue'],
        orders_count=metrics['orders_count'],
        avg_check=metrics['avg_check'],
        new_clients=metrics['new_clients'],
        top_products=metrics['top_products'],
        recommendations=recommendations,
        source=source,
    )


def build_daily_recommendations(metrics):
    recommendations = []
    top_products = metrics.get('top_products') or []
    revenue = metrics.get('revenue') or Decimal('0')
    orders_count = metrics.get('orders_count') or 0
    avg_check = metrics.get('avg_check') or Decimal('0')

    if top_products:
        leader = top_products[0]
        recommendations.append(
            f'Подготовить дополнительный запас товара "{leader["product_name"]}" — он лидирует по продажам.'
        )
    if not orders_count:
        recommendations.append('За вчера не было заказов: проверьте рекламные каналы и доступность меню.')
    elif avg_check < Decimal('700'):
        recommendations.append('Средний чек ниже 700 руб.: стоит предложить наборы, комбо или допродажи к напиткам.')
    if revenue > Decimal('0') and orders_count >= 3:
        recommendations.append('День был активным: сохраните ассортимент и график выпечки для похожих дней недели.')
    if not recommendations:
        recommendations.append('Данных достаточно для наблюдения, критичных отклонений не найдено.')
    return recommendations


def render_daily_report_text(daily_metrics):
    if daily_metrics.top_products:
        top = ', '.join(f"{item['product_name']} ({item['quantity']})" for item in daily_metrics.top_products)
    else:
        top = 'Нет данных'

    recommendations = '\n'.join(f'- {item}' for item in daily_metrics.recommendations)

    return (
        f"Ежедневный отчет ButterCafe за {daily_metrics.report_date}\n"
        f"Источник метрик: {daily_metrics.source}\n\n"
        f"Выручка за день: {daily_metrics.revenue:.2f} руб.\n"
        f"Количество заказов: {daily_metrics.orders_count}\n"
        f"Средний чек: {daily_metrics.avg_check:.2f} руб.\n"
        f"Новых клиентов: {daily_metrics.new_clients}\n"
        f"Топ-3 товара: {top}\n\n"
        f"Рекомендации:\n{recommendations}\n"
    )


def render_daily_report_html(daily_metrics):
    if daily_metrics.top_products:
        top_rows = ''.join(
            f'<tr><td>{escape(item.get("product_name") or "Без названия")}</td><td style="text-align:right">{int(item.get("quantity") or 0)}</td></tr>'
            for item in daily_metrics.top_products
        )
    else:
        top_rows = '<tr><td colspan="2">Нет данных</td></tr>'

    recommendations = ''.join(f'<li>{escape(item)}</li>' for item in daily_metrics.recommendations)

    return f"""
<!doctype html>
<html lang="ru">
<body style="margin:0;padding:0;background:#f6f1e7;font-family:Arial,sans-serif;color:#2d221c;">
  <div style="max-width:720px;margin:0 auto;padding:24px;">
    <div style="background:#6c2a17;color:#fff;border-radius:14px;padding:24px;">
      <h1 style="margin:0;font-size:26px;">Ежедневный отчет ButterCafe</h1>
      <p style="margin:8px 0 0;color:#f6eadf;">{daily_metrics.report_date} · источник: {daily_metrics.source}</p>
    </div>

    <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:18px 0;">
      <div style="background:#fffaf3;border:1px solid #e0d3c0;border-radius:12px;padding:16px;">
        <div style="color:#785957;font-size:12px;font-weight:bold;text-transform:uppercase;">Выручка</div>
        <div style="font-size:28px;font-weight:bold;color:#6c2a17;">{daily_metrics.revenue:.2f} руб.</div>
      </div>
      <div style="background:#fffaf3;border:1px solid #e0d3c0;border-radius:12px;padding:16px;">
        <div style="color:#785957;font-size:12px;font-weight:bold;text-transform:uppercase;">Заказы</div>
        <div style="font-size:28px;font-weight:bold;color:#6c2a17;">{daily_metrics.orders_count}</div>
      </div>
      <div style="background:#fffaf3;border:1px solid #e0d3c0;border-radius:12px;padding:16px;">
        <div style="color:#785957;font-size:12px;font-weight:bold;text-transform:uppercase;">Средний чек</div>
        <div style="font-size:28px;font-weight:bold;color:#6c2a17;">{daily_metrics.avg_check:.2f} руб.</div>
      </div>
      <div style="background:#fffaf3;border:1px solid #e0d3c0;border-radius:12px;padding:16px;">
        <div style="color:#785957;font-size:12px;font-weight:bold;text-transform:uppercase;">Новые клиенты</div>
        <div style="font-size:28px;font-weight:bold;color:#6c2a17;">{daily_metrics.new_clients}</div>
      </div>
    </div>

    <div style="background:#fffaf3;border:1px solid #e0d3c0;border-radius:12px;padding:18px;margin-bottom:14px;">
      <h2 style="margin:0 0 12px;color:#6c2a17;font-size:20px;">Топ товаров</h2>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr><th style="text-align:left;border-bottom:1px solid #e0d3c0;padding:8px;">Товар</th><th style="text-align:right;border-bottom:1px solid #e0d3c0;padding:8px;">Количество</th></tr></thead>
        <tbody>{top_rows}</tbody>
      </table>
    </div>

    <div style="background:#fffaf3;border:1px solid #e0d3c0;border-radius:12px;padding:18px;">
      <h2 style="margin:0 0 12px;color:#6c2a17;font-size:20px;">Рекомендации</h2>
      <ul style="margin:0;padding-left:20px;line-height:1.6;">{recommendations}</ul>
    </div>
  </div>
</body>
</html>
"""


def save_daily_report_files(daily_metrics, text_body=None, html_body=None):
    day, month, year = daily_metrics.report_date.split('.')
    report_dir = Path(settings.ANALYTICS_EXPORT_ROOT) / 'reports' / year / month / day
    report_dir.mkdir(parents=True, exist_ok=True)

    text_path = report_dir / 'daily_report.txt'
    html_path = report_dir / 'daily_report.html'

    text_path.write_text(text_body or render_daily_report_text(daily_metrics), encoding='utf-8')
    html_path.write_text(html_body or render_daily_report_html(daily_metrics), encoding='utf-8')

    return text_path, html_path
