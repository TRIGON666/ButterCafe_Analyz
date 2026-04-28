import json
import math
from datetime import datetime, timedelta
from io import BytesIO

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Sum
from django.db.models.functions import ExtractHour, TruncDate, TruncMonth, TruncWeek
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from cafe.models import EventLog, Order, OrderItem
from cafe.services.metabase import build_dashboard_embed_url, configured_missing_settings


PERIOD_PRESETS = {
    'today': 0,
    '7d': 6,
    '14d': 13,
    '30d': 29,
    '90d': 89,
}


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _resolve_period(request):
    end_date = _parse_date(request.GET.get('end')) or timezone.localdate()
    period = request.GET.get('period', '14d')
    start_date = _parse_date(request.GET.get('start'))

    if period == 'month':
        start_date = end_date.replace(day=1)
    elif period == 'week':
        start_date = end_date - timedelta(days=end_date.weekday())
    elif period == 'custom' and start_date:
        period = 'custom'
    else:
        start_date = end_date - timedelta(days=PERIOD_PRESETS.get(period, 13))
        period = period if period in PERIOD_PRESETS else '14d'

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    group_by = request.GET.get('group_by', 'day')
    if group_by not in {'day', 'week', 'month'}:
        group_by = 'day'

    return start_date, end_date, period, group_by


def _group_config(group_by):
    if group_by == 'week':
        return TruncWeek('created_at'), '%d.%m'
    if group_by == 'month':
        return TruncMonth('created_at'), '%m.%Y'
    return TruncDate('created_at'), '%d.%m'


def _weighted_forecast(end_date):
    forecast_start = end_date - timedelta(days=27)
    item_qs = OrderItem.objects.filter(
        order__created_at__date__gte=forecast_start,
        order__created_at__date__lte=end_date,
    ).exclude(order__status='cancelled')
    orders_qs = Order.objects.filter(
        created_at__date__gte=forecast_start,
        created_at__date__lte=end_date,
    ).exclude(status='cancelled')

    weights = [1, 2, 3, 5]
    weekly_revenue = []
    weekly_orders = []
    weekday_orders = {index: [] for index in range(7)}
    product_scores = {}
    product_week_values = {}

    for index, weight in enumerate(weights):
        week_start = forecast_start + timedelta(days=index * 7)
        week_end = week_start + timedelta(days=6)
        week_orders = orders_qs.filter(created_at__date__gte=week_start, created_at__date__lte=week_end)
        totals = week_orders.aggregate(revenue=Sum('total'), orders_count=Count('id'))

        weekly_revenue.append(float(totals['revenue'] or 0))
        weekly_orders.append(int(totals['orders_count'] or 0))

        for day_offset in range(7):
            day = week_start + timedelta(days=day_offset)
            count = week_orders.filter(created_at__date=day).count()
            weekday_orders[day_offset].append(count)

        week_products = (
            item_qs.filter(order__created_at__date__gte=week_start, order__created_at__date__lte=week_end)
            .values('product__name')
            .annotate(quantity=Sum('quantity'))
        )
        for item in week_products:
            name = item['product__name'] or 'Без названия'
            quantity = float(item['quantity'] or 0)
            product_scores[name] = product_scores.get(name, 0) + quantity * weight
            product_week_values.setdefault(name, [0, 0, 0, 0])[index] = quantity

    weight_sum = sum(weights)
    next_week_revenue = sum(value * weights[index] for index, value in enumerate(weekly_revenue)) / weight_sum if weight_sum else 0
    next_week_orders = sum(value * weights[index] for index, value in enumerate(weekly_orders)) / weight_sum if weight_sum else 0

    daily_forecast = []
    next_week_start = end_date + timedelta(days=1)
    for day_offset in range(7):
        values = weekday_orders[day_offset]
        weighted_count = sum(values[index] * weights[index] for index in range(len(weights))) / weight_sum if weight_sum else 0
        day = next_week_start + timedelta(days=day_offset)
        daily_forecast.append(
            {
                'label': day.strftime('%d.%m'),
                'orders': int(round(weighted_count)),
            }
        )

    forecast_products = []
    for name, score in sorted(product_scores.items(), key=lambda pair: pair[1], reverse=True)[:8]:
        values = product_week_values.get(name, [0, 0, 0, 0])
        expected = sum(values[index] * weights[index] for index in range(len(weights))) / weight_sum if weight_sum else 0
        trend = 'stable'
        if values[-1] > values[-2] if len(values) > 1 else False:
            trend = 'up'
        elif values[-1] < values[-2] if len(values) > 1 else False:
            trend = 'down'
        forecast_products.append(
            {
                'name': name,
                'expected_quantity': int(math.ceil(expected)),
                'score': round(score, 2),
                'trend': trend,
            }
        )

    return {
        'next_week_revenue': round(next_week_revenue, 2),
        'next_week_orders': int(round(next_week_orders)),
        'forecast_products': forecast_products,
        'daily_forecast': daily_forecast,
        'forecast_labels': [item['label'] for item in daily_forecast],
        'forecast_orders': [item['orders'] for item in daily_forecast],
    }


def _build_analytics_payload(request):
    start_date, end_date, period, group_by = _resolve_period(request)
    trunc_expression, label_format = _group_config(group_by)

    orders_qs = Order.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    sales_orders_qs = orders_qs.exclude(status='cancelled')
    items_qs = OrderItem.objects.filter(
        order__created_at__date__gte=start_date,
        order__created_at__date__lte=end_date,
    ).exclude(order__status='cancelled')

    daily_stats = list(
        sales_orders_qs.annotate(period=trunc_expression)
        .values('period')
        .annotate(revenue=Sum('total'), orders_count=Count('id'))
        .order_by('period')
    )
    daily_labels = [item['period'].strftime(label_format) for item in daily_stats]
    daily_revenue = [float(item['revenue'] or 0) for item in daily_stats]
    daily_orders = [item['orders_count'] for item in daily_stats]

    line_revenue = ExpressionWrapper(
        F('quantity') * F('price'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    top_products = list(
        items_qs.alias(line_revenue=line_revenue)
        .values('product__name')
        .annotate(
            quantity=Sum('quantity'),
            revenue=Sum('line_revenue'),
        )
        .order_by('-quantity', 'product__name')[:8]
    )
    top_product_labels = [item['product__name'] for item in top_products]
    top_product_values = [int(item['quantity'] or 0) for item in top_products]

    abc_products = []
    product_revenue_rows = list(
        items_qs.alias(line_revenue=line_revenue)
        .values('product__name')
        .annotate(
            quantity=Sum('quantity'),
            revenue=Sum('line_revenue'),
        )
        .order_by('-revenue', 'product__name')
    )
    products_revenue_total = sum(float(item['revenue'] or 0) for item in product_revenue_rows)
    cumulative_revenue = 0
    for item in product_revenue_rows[:12]:
        revenue = float(item['revenue'] or 0)
        share = round((revenue / products_revenue_total * 100), 2) if products_revenue_total else 0
        cumulative_revenue += revenue
        cumulative_share = (cumulative_revenue / products_revenue_total * 100) if products_revenue_total else 0
        abc_class = 'A'
        if cumulative_share > 95:
            abc_class = 'C'
        elif cumulative_share > 80:
            abc_class = 'B'
        abc_products.append(
            {
                'name': item['product__name'] or 'Без названия',
                'quantity': int(item['quantity'] or 0),
                'revenue': revenue,
                'share': share,
                'cumulative_share': round(min(cumulative_share, 100), 2),
                'abc_class': abc_class,
            }
        )

    events_qs = EventLog.objects.filter(timestamp__date__gte=start_date, timestamp__date__lte=end_date)
    events_stats = list(
        events_qs.values('event_type')
        .annotate(total=Count('id'))
        .order_by('event_type')
    )
    event_labels = [item['event_type'] for item in events_stats]
    event_values = [item['total'] for item in events_stats]

    event_totals = {item['event_type']: item['total'] for item in events_stats}
    cart_session_keys = set()
    order_session_keys = set()
    for event in events_qs.filter(event_type__in=['added_to_cart', 'order_created']).values('event_type', 'metadata_json'):
        metadata = event.get('metadata_json') or {}
        session_key = metadata.get('cart_session_key')
        if not session_key:
            continue
        if event['event_type'] == 'added_to_cart':
            cart_session_keys.add(session_key)
        elif event['event_type'] == 'order_created':
            order_session_keys.add(session_key)

    if cart_session_keys:
        cart_additions = len(cart_session_keys)
        created_orders_events = len(cart_session_keys & order_session_keys)
        cart_to_order_conversion = round(created_orders_events / cart_additions * 100, 2)
        funnel_cart_label = 'Сессий с добавлением в корзину'
        funnel_order_label = 'Сессий с оформленным заказом'
        funnel_conversion_label = 'Конверсия сессий с корзиной в заказ'
    else:
        cart_additions = int(event_totals.get('added_to_cart', 0))
        created_orders_events = int(event_totals.get('order_created', 0))
        cart_to_order_conversion = round(created_orders_events / cart_additions * 100, 2) if cart_additions else 0
        funnel_cart_label = 'Добавлений товаров в корзину'
        funnel_order_label = 'Событий оформления заказа'
        funnel_conversion_label = 'Конверсия добавлений в корзину в заказ'

    status_stats = list(
        orders_qs.values('status')
        .annotate(orders_count=Count('id'), revenue=Sum('total'))
        .order_by('-orders_count', 'status')
    )
    status_labels = dict(Order.STATUS_CHOICES)
    for item in status_stats:
        item['status_label'] = status_labels.get(item['status'], item['status'])

    delivery_stats = list(
        sales_orders_qs.values('delivery_type')
        .annotate(orders_count=Count('id'), revenue=Sum('total'))
        .order_by('-orders_count', 'delivery_type')
    )
    delivery_labels = dict(Order.DELIVERY_CHOICES)
    for item in delivery_stats:
        item['delivery_label'] = delivery_labels.get(item['delivery_type'], item['delivery_type'])

    rfm_customers = list(
        sales_orders_qs.filter(user__isnull=False)
        .values('user__username')
        .annotate(
            last_order_at=Max('created_at'),
            frequency=Count('id'),
            monetary=Sum('total'),
        )
        .order_by('-monetary', '-frequency', 'user__username')[:10]
    )

    hourly_stats = list(
        sales_orders_qs.annotate(hour=ExtractHour('created_at'))
        .values('hour')
        .annotate(total=Count('id'))
        .order_by('hour')
    )
    hourly_labels = [f"{int(item['hour']):02d}:00" for item in hourly_stats if item['hour'] is not None]
    hourly_values = [item['total'] for item in hourly_stats if item['hour'] is not None]

    totals = sales_orders_qs.aggregate(revenue=Sum('total'), orders_count=Count('id'))
    total_revenue = float(totals['revenue'] or 0)
    total_orders = int(totals['orders_count'] or 0)
    avg_check = round(total_revenue / total_orders, 2) if total_orders else 0

    forecast = _weighted_forecast(end_date)

    recommendations = []
    if forecast['forecast_products']:
        leader = forecast['forecast_products'][0]
        recommendations.append(
            f'Подготовить запас товара "{leader["name"]}" на неделю: прогноз {leader["expected_quantity"]} шт.'
        )
    if top_product_labels:
        recommendations.append(f'Сделать акцент в витрине на товар "{top_product_labels[0]}" как лидер продаж периода.')
    if cart_additions and cart_to_order_conversion < 40:
        recommendations.append('Конверсия корзины в заказ ниже 40%: стоит проверить оформление заказа и условия доставки.')
    if total_orders and avg_check < 700:
        recommendations.append('Средний чек ниже 700 руб.: можно предложить наборы или комбо-позиции.')
    if not recommendations:
        recommendations.append('Данных пока недостаточно для автоматических рекомендаций.')

    return {
        'start_date': start_date,
        'end_date': end_date,
        'period': period,
        'group_by': group_by,
        'daily_stats': daily_stats,
        'top_products': top_products,
        'abc_products': abc_products,
        'events_stats': events_stats,
        'status_stats': status_stats,
        'delivery_stats': delivery_stats,
        'rfm_customers': rfm_customers,
        'cart_additions': cart_additions,
        'created_orders_events': created_orders_events,
        'cart_to_order_conversion': cart_to_order_conversion,
        'funnel_cart_label': funnel_cart_label,
        'funnel_order_label': funnel_order_label,
        'funnel_conversion_label': funnel_conversion_label,
        'recommendations': recommendations,
        'hourly_stats': hourly_stats,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_check': avg_check,
        'daily_labels': daily_labels,
        'daily_revenue': daily_revenue,
        'daily_orders': daily_orders,
        'top_product_labels': top_product_labels,
        'top_product_values': top_product_values,
        'event_labels': event_labels,
        'event_values': event_values,
        'hourly_labels': hourly_labels,
        'hourly_values': hourly_values,
        **forecast,
    }


@staff_member_required
def analytics_dashboard(request):
    payload = _build_analytics_payload(request)

    context = {
        **payload,
        'title': 'Аналитика ButterCafe',
        'subtitle': f'{payload["start_date"].strftime("%d.%m.%Y")} - {payload["end_date"].strftime("%d.%m.%Y")}',
        'daily_labels_json': json.dumps(payload['daily_labels'], ensure_ascii=False),
        'daily_revenue_json': json.dumps(payload['daily_revenue']),
        'daily_orders_json': json.dumps(payload['daily_orders']),
        'top_product_labels_json': json.dumps(payload['top_product_labels'], ensure_ascii=False),
        'top_product_values_json': json.dumps(payload['top_product_values']),
        'event_labels_json': json.dumps(payload['event_labels'], ensure_ascii=False),
        'event_values_json': json.dumps(payload['event_values']),
        'hourly_labels_json': json.dumps(payload['hourly_labels'], ensure_ascii=False),
        'hourly_values_json': json.dumps(payload['hourly_values']),
        'forecast_labels_json': json.dumps(payload['forecast_labels'], ensure_ascii=False),
        'forecast_orders_json': json.dumps(payload['forecast_orders']),
    }
    return render(request, 'admin/analytics_dashboard.html', context)


@staff_member_required
def metabase_dashboard(request):
    missing_settings = configured_missing_settings()
    context = {
        'title': 'Metabase ButterCafe',
        'metabase_url': build_dashboard_embed_url() if not missing_settings else None,
        'missing_settings': missing_settings,
        'metabase_base_url': getattr(settings, 'METABASE_URL', ''),
        'metabase_dashboard_id': getattr(settings, 'METABASE_DASHBOARD_ID', ''),
        'metabase_card_ids': {
            'revenue': getattr(settings, 'METABASE_REVENUE_CARD_ID', ''),
            'orders': getattr(settings, 'METABASE_ORDERS_CARD_ID', ''),
            'avg_check': getattr(settings, 'METABASE_AVG_CHECK_CARD_ID', ''),
            'new_clients': getattr(settings, 'METABASE_NEW_CLIENTS_CARD_ID', ''),
            'top_products': getattr(settings, 'METABASE_TOP_PRODUCTS_CARD_ID', ''),
        },
    }
    return render(request, 'admin/metabase_dashboard.html', context)


@staff_member_required
def analytics_dashboard_pdf(request):
    payload = _build_analytics_payload(request)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    story = [
        Paragraph('ButterCafe Analytics Report', styles['Title']),
        Paragraph(f"Period: {payload['start_date'].strftime('%d.%m.%Y')} - {payload['end_date'].strftime('%d.%m.%Y')}", styles['Normal']),
        Spacer(1, 8),
    ]

    kpi_table = Table(
        [
            ['Revenue', 'Orders', 'Average check', 'Next week orders'],
            [
                f"{payload['total_revenue']:.2f} RUB",
                str(payload['total_orders']),
                f"{payload['avg_check']:.2f} RUB",
                str(payload['next_week_orders']),
            ],
        ],
        colWidths=[42 * mm, 42 * mm, 42 * mm, 42 * mm],
    )
    kpi_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0e2d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#4f1d10')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7b89f')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 12))

    forecast_rows = [['Product forecast', 'Expected qty', 'Trend']]
    for item in payload['forecast_products']:
        forecast_rows.append([item['name'], str(item['expected_quantity']), item['trend']])
    if len(forecast_rows) == 1:
        forecast_rows.append(['No data', '-', '-'])

    forecast_table = Table(forecast_rows, colWidths=[105 * mm, 32 * mm, 32 * mm])
    forecast_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0e2d2')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7b89f')),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
        )
    )
    story.append(Paragraph('Next week forecast', styles['Heading2']))
    story.append(forecast_table)
    story.append(Spacer(1, 10))

    top_products_rows = [['Product', 'Qty']]
    for item in payload['top_products']:
        top_products_rows.append([item['product__name'], str(int(item['quantity'] or 0))])
    if len(top_products_rows) == 1:
        top_products_rows.append(['No data', '-'])

    top_table = Table(top_products_rows, colWidths=[130 * mm, 40 * mm])
    top_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0e2d2')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7b89f')),
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ]
        )
    )
    story.append(Paragraph('Top products', styles['Heading2']))
    story.append(top_table)

    doc.build(story)

    buffer.seek(0)
    filename = f"buttercafe_analytics_{payload['end_date'].strftime('%Y%m%d')}.pdf"
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
