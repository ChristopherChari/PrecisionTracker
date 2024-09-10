from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('CampaignTracker', '0010_alter_campaign_channel_delete_channel'),
        ('CampaignTracker', '0011_alter_target_unique_together_target_channel_and_more'),
    ]

    operations = [
        # Copy the combined changes from both 0010 and 0011 migrations here
        # For example:
        migrations.AlterField(
            model_name='campaign',
            name='channel',
            field=models.CharField(choices=[('Google', 'Google'), ('Stackadapt', 'Stackadapt')], default='Google', max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name='target',
            unique_together={('product', 'month', 'client', 'campaign_type', 'channel')},
        ),
        # Include any other operations from both migrations
    ]
