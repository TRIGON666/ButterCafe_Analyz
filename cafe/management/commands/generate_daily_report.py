from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail

from cafe.services.reporting import get_daily_metrics, render_daily_report_text


class Command(BaseCommand):
    help = 'Generates daily analytics report and sends it to owner email'

    def handle(self, *args, **options):
        if not settings.OWNER_REPORT_EMAIL:
            self.stdout.write(self.style.ERROR('OWNER_REPORT_EMAIL is not configured'))
            return

        metrics = get_daily_metrics()
        report_text = render_daily_report_text(metrics)
        subject = f'ButterCafe: ежедневный отчет за {metrics.report_date}'

        sent_count = send_mail(
            subject=subject,
            message=report_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.OWNER_REPORT_EMAIL],
            fail_silently=False,
        )

        if sent_count:
            self.stdout.write(self.style.SUCCESS(f'Report sent to {settings.OWNER_REPORT_EMAIL}'))
        else:
            self.stdout.write(self.style.WARNING('Report was not sent'))
