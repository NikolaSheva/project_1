# Generated by Django 5.2 on 2025-05-22 19:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("watch", "0019_remove_filterpreset_condition_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WatchItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("price_id", models.IntegerField(blank=True, null=True)),
            ],
        ),
    ]
