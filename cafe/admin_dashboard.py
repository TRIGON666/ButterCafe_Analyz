import json
import math
from datetime import datetime, timedelta
from io import BytesIO

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
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
        pass
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
    item_qs = OrderItem.objects.filter(order__created_at__date__gte=forecast_start, order__created_at__date__lte=end_date)
    orders_qs = Order.objects.filter(created_at__date__gte=forecast_start, created_at__date__lte=end_date)

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
    items_qs = OrderItem.objects.filter(order__created_at__date__gte=start_date, order__created_at__date__lte=end_date)

    daily_stats = list(
        orders_qs.annotate(period=trunc_expression)
        .values('period')
        .annotate(revenue=Sum('total'), orders_count=Count('id'))
        .order_by('period')
    )
    daily_labels = [item['period'].strftime(label_format) for item in daily_stats]
    daily_revenue = [float(item['revenue'] or 0) for item in daily_stats]
    daily_orders = [item['orders_count'] for item in daily_stats]

    top_products = list(
        items_qs.values('product__name')
        .annotate(quantity=Sum('quantity'), revenue=Sum('price'))
        .order_by('-quantity', 'product__name')[:8]
    )
    top_product_labels = [item['product__name'] for item in top_products]
    top_product_values = [int(item['quantity'] or 0) for item in top_products]

    events_stats = list(
        EventLog.objects.filter(timestamp__date__gte=start_date, timestamp__date__lte=end_date)
        .values('event_type')
        .annotate(total=Count('id'))
        .order_by('event_type')
    )
    event_labels = [item['event_type'] for item in events_stats]
    event_values = [item['total'] for item in events_stats]

    hourly_stats = list(
        orders_qs.annotate(hour=ExtractHour('created_at'))
        .values('hour')
        .annotate(total=Count('id'))
        .order_by('hour')
    )
    hourly_labels = [f"{int(item['hour']):02d}:00" for item in hourly_stats if item['hour'] is not None]
    hourly_values = [item['total'] for item in hourly_stats if item['hour'] is not None]

    totals = orders_qs.aggregate(revenue=Sum('total'), orders_count=Count('id'))
    total_revenue = float(totals['revenue'] or 0)
    total_orders = int(totals['orders_count'] or 0)
    avg_check = round(total_revenue / total_orders, 2) if total_orders else 0

    forecast = _weighted_forecast(end_date)

    return {
        'start_date': start_date,
        'end_date': end_date,
        'period': period,
        'group_by': group_by,
        'daily_stats': daily_stats,
        'top_products': top_products,
        'events_stats': events_stats,
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
