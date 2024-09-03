from django.db import models

class Client(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Channel(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Campaign(models.Model):
    CAMPAIGN_TYPE_CHOICES = [
        ('Video', 'Video'),
        ('Display', 'Display'),
        ('Search', 'Search'),
    ]

    name = models.CharField(max_length=100)
    user_friendly_name = models.CharField(max_length=255, null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    campaign_type = models.CharField(max_length=10, choices=CAMPAIGN_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    spend = models.DecimalField(max_digits=10, decimal_places=2)
    impressions = models.IntegerField()
    clicks = models.IntegerField()
    ctr = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cpc = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    conversions = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Calculate CTR and CPC
        self.ctr = (self.clicks / self.impressions * 100) if self.impressions > 0 else 0
        self.cpc = (self.spend / self.clicks) if self.clicks > 0 else 0
        super(Campaign, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

class MonthlyData(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    month = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    spend = models.DecimalField(max_digits=10, decimal_places=2)
    impressions = models.IntegerField()
    clicks = models.IntegerField()
    conversions = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.campaign.name} - {self.month}"
