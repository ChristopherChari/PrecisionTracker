# Generated by Django 5.1 on 2024-09-03 15:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('CampaignTracker', '0002_campaign_cpc_campaign_ctr'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='user_friendly_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
