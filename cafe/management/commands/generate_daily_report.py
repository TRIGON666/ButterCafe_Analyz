from smtplib import SMTPException

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives

from cafe.services.reporting import (
    get_daily_metrics,
    render_daily_report_html,
    render_daily_report_text,
    save_daily_report_files,
)


class Command(BaseCommand):
    help = 'Generates daily analytics report and sends it to owner email'

    def handle(self, *args, **options):
        metrics = get_daily_metrics()
        report_text = render_daily_report_text(metrics)
        report_html = render_daily_report_html(metrics)
        subject = f'ButterCafe: ежедневный отчет за {metrics.report_date}'

        if not settings.OWNER_REPORT_EMAIL:
            text_path, html_path = save_daily_report_files(metrics, report_text, report_html)
            self.stdout.write(self.style.ERROR('OWNER_REPORT_EMAIL is not configured'))
            self.stdout.write(self.style.WARNING(f'Report saved locally: {text_path} and {html_path}'))
            return

        email = EmailMultiAlternatives(
            subject=subject,
            body=report_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.OWNER_REPORT_EMAIL],
        )
        email.attach_alternative(report_html, 'text/html')
        try:
            sent_count = email.send(fail_silently=False)
        except (SMTPException, OSError) as exc:
            text_path, html_path = save_daily_report_files(metrics, report_text, report_html)
            self.stdout.write(self.style.ERROR(f'Report was not sent: {exc}'))
            self.stdout.write(self.style.WARNING(f'Report saved locally: {text_path} and {html_path}'))
            return

        if sent_count:
            self.stdout.write(self.style.SUCCESS(f'Report sent to {settings.OWNER_REPORT_EMAIL}'))
        else:
            text_path, html_path = save_daily_report_files(metrics, report_text, report_html)
            self.stdout.write(self.style.WARNING('Report was not sent'))
            self.stdout.write(self.style.WARNING(f'Report saved locally: {text_path} and {html_path}'))
