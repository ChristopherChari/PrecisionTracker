# Generated by Django 5.1 on 2024-09-10 11:51

from django.db import migrations, models


def set_default_channel(apps, schema_editor):
    Target = apps.get_model('CampaignTracker', 'Target')
    Target.objects.all().update(channel='Google')

class Migration(migrations.Migration):

    dependencies = [
        # Add your previous migration dependencies here
    ]

    operations = [
        migrations.AddField(
            model_name='target',
            name='channel',
            field=models.CharField(choices=[('Google', 'Google'), ('Stackadapt', 'Stackadapt')], default='Google', max_length=20),
        ),
        migrations.RunPython(set_default_channel),  # Add this line to update existing rows
    ]