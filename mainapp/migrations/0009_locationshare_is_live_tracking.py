# Generated by Django 5.0.7 on 2025-04-05 08:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mainapp', '0008_booking_extension_payment_intent_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='locationshare',
            name='is_live_tracking',
            field=models.BooleanField(default=False),
        ),
    ]
