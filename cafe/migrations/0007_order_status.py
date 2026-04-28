from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cafe', '0006_alter_order_options_rename_created_order_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('new', 'Новый'),
                    ('confirmed', 'Подтвержден'),
                    ('cooking', 'Готовится'),
                    ('ready', 'Готов'),
                    ('delivered', 'Доставлен'),
                    ('cancelled', 'Отменен'),
                ],
                default='new',
                max_length=20,
                verbose_name='Статус заказа',
            ),
        ),
    ]
