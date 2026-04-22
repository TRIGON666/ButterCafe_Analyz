import json
from datetime import timedelta
from io import BytesIO

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie

from cafe.models import EventLog, Order, OrderItem


def _build_analytics_payload():
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=13)

    orders_qs = Order.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

    daily_stats = list(
        orders_qs.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(revenue=Sum('total'), orders_count=Count('id'))
        .order_by('day')
    )

    daily_labels = [item['day'].strftime('%d.%m') for item in daily_stats]
    daily_revenue = [float(item['revenue'] or 0) for item in daily_stats]
    daily_orders = [item['orders_count'] for item in daily_stats]

    top_products = list(
        OrderItem.objects.filter(order__created_at__date__gte=start_date, order__created_at__date__lte=end_date)
        .values('product__name')
        .annotate(quantity=Sum('quantity'))
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

    return {
        'start_date': start_date,
        'end_date': end_date,
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
    }


@staff_member_required
def analytics_dashboard(request):
    payload = _build_analytics_payload()

    context = {
        'title': 'Аналитика ButterCafe',
        'subtitle': f'Период: {payload["start_date"].strftime("%d.%m.%Y")} - {payload["end_date"].strftime("%d.%m.%Y")}',
        'total_revenue': payload['total_revenue'],
        'total_orders': payload['total_orders'],
        'avg_check': payload['avg_check'],
        'daily_labels': json.dumps(payload['daily_labels'], ensure_ascii=False),
        'daily_revenue': json.dumps(payload['daily_revenue']),
        'daily_orders': json.dumps(payload['daily_orders']),
        'top_product_labels': json.dumps(payload['top_product_labels'], ensure_ascii=False),
        'top_product_values': json.dumps(payload['top_product_values']),
        'event_labels': json.dumps(payload['event_labels'], ensure_ascii=False),
        'event_values': json.dumps(payload['event_values']),
        'hourly_labels': json.dumps(payload['hourly_labels'], ensure_ascii=False),
        'hourly_values': json.dumps(payload['hourly_values']),
    }
    return render(request, 'admin/analytics_dashboard.html', context)


@staff_member_required
def analytics_dashboard_pdf(request):
    payload = _build_analytics_payload()

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
    story = []

    story.append(Paragraph('ButterCafe Analytics Report', styles['Title']))
    story.append(
        Paragraph(
            f"Period: {payload['start_date'].strftime('%d.%m.%Y')} - {payload['end_date'].strftime('%d.%m.%Y')}",
            styles['Normal'],
        )
    )
    story.append(Spacer(1, 8))

    kpi_table = Table(
        [
            ['Total revenue', 'Total orders', 'Average check'],
            [f"{payload['total_revenue']:.2f} RUB", str(payload['total_orders']), f"{payload['avg_check']:.2f} RUB"],
        ],
        colWidths=[56 * mm, 56 * mm, 56 * mm],
    )
    kpi_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eceff4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 1), (-1, 1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph('Dashboards', styles['Heading2']))

    def _line_chart(title, labels, values, color_hex='#2b6cb0'):
        chart_width = 170 * mm
        chart_height = 58 * mm
        drawing = Drawing(chart_width, chart_height)
        drawing.add(String(0, chart_height - 4, title, fontName='Helvetica-Bold', fontSize=10))

        if not labels or not values:
            drawing.add(String(0, chart_height / 2, 'No data', fontName='Helvetica', fontSize=10))
            return drawing

        line = HorizontalLineChart()
        line.x = 35
        line.y = 15
        line.height = chart_height - 30
        line.width = chart_width - 50
        line.data = [list(values)]
        line.lines[0].strokeColor = colors.HexColor(color_hex)
        line.lines[0].strokeWidth = 2
        line.categoryAxis.categoryNames = [str(label) for label in labels]
        line.categoryAxis.labels.boxAnchor = 'ne'
        line.categoryAxis.labels.angle = 30
        line.categoryAxis.labels.fontSize = 6
        line.valueAxis.forceZero = True
        line.valueAxis.labels.fontSize = 7
        line.joinedLines = 1
        drawing.add(line)
        return drawing

    def _bar_chart(title, labels, values, color_hex='#dd6b20'):
        chart_width = 170 * mm
        chart_height = 58 * mm
        drawing = Drawing(chart_width, chart_height)
        drawing.add(String(0, chart_height - 4, title, fontName='Helvetica-Bold', fontSize=10))

        if not labels or not values:
            drawing.add(String(0, chart_height / 2, 'No data', fontName='Helvetica', fontSize=10))
            return drawing

        bar = VerticalBarChart()
        bar.x = 35
        bar.y = 15
        bar.height = chart_height - 30
        bar.width = chart_width - 50
        bar.data = [list(values)]
        bar.barWidth = 8
        bar.groupSpacing = 8
        bar.bars[0].fillColor = colors.HexColor(color_hex)
        bar.categoryAxis.categoryNames = [str(label) for label in labels]
        bar.categoryAxis.labels.boxAnchor = 'ne'
        bar.categoryAxis.labels.angle = 30
        bar.categoryAxis.labels.fontSize = 6
        bar.valueAxis.forceZero = True
        bar.valueAxis.labels.fontSize = 7
        drawing.add(bar)
        return drawing

    def _pie_chart(title, labels, values):
        chart_width = 170 * mm
        chart_height = 62 * mm
        drawing = Drawing(chart_width, chart_height)
        drawing.add(String(0, chart_height - 4, title, fontName='Helvetica-Bold', fontSize=10))

        if not labels or not values:
            drawing.add(String(0, chart_height / 2, 'No data', fontName='Helvetica', fontSize=10))
            return drawing

        pie = Pie()
        pie.x = 10
        pie.y = 5
        pie.width = 60 * mm
        pie.height = 45 * mm
        pie.data = [float(v) for v in values]
        pie.labels = [str(label) for label in labels]
        pie.slices.strokeWidth = 0.5
        pie.slices[0].popout = 3
        pie.sideLabels = True
        pie.simpleLabels = False
        drawing.add(pie)
        return drawing

    story.append(_line_chart('Revenue by day', payload['daily_labels'], payload['daily_revenue']))
    story.append(Spacer(1, 6))
    story.append(_bar_chart('Orders by hour', payload['hourly_labels'], payload['hourly_values']))
    story.append(Spacer(1, 6))
    story.append(_bar_chart('Top products by quantity', payload['top_product_labels'], payload['top_product_values'], color_hex='#2f855a'))
    story.append(Spacer(1, 6))
    story.append(_pie_chart('Events distribution', payload['event_labels'], payload['event_values']))
    story.append(Spacer(1, 10))

    story.append(Paragraph('Detailed tables', styles['Heading2']))

    top_products_rows = [['Product', 'Qty']]
    for item in payload['top_products']:
        top_products_rows.append([item['product__name'], str(int(item['quantity'] or 0))])
    if len(top_products_rows) == 1:
        top_products_rows.append(['No data', '-'])

    top_table = Table(top_products_rows, colWidths=[130 * mm, 40 * mm])
    top_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#edf2f7')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
        )
    )
    story.append(top_table)
    story.append(Spacer(1, 8))

    daily_rows = [['Date', 'Revenue (RUB)', 'Orders']]
    for item in payload['daily_stats']:
        daily_rows.append(
            [
                item['day'].strftime('%d.%m.%Y'),
                f"{float(item['revenue'] or 0):.2f}",
                str(item['orders_count']),
            ]
        )
    if len(daily_rows) == 1:
        daily_rows.append(['No data', '-', '-'])

    daily_table = Table(daily_rows, colWidths=[50 * mm, 70 * mm, 50 * mm])
    daily_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#edf2f7')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
        )
    )
    story.append(daily_table)

    doc.build(story)

    buffer.seek(0)
    filename = f"buttercafe_analytics_{payload['end_date'].strftime('%Y%m%d')}.pdf"
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
