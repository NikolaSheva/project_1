# Generated by Django 5.2 on 2025-05-13 14:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("watch", "0015_alter_product_cities"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="city",
            name="slug",
        ),
    ]
