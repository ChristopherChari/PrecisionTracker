from django.db import models

class Client(models.Model):
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

    GOOGLE = 'Google'
    STACKADAPT = 'Stackadapt'
    
    CHANNEL_CHOICES = [
        (GOOGLE, 'Google'),
        (STACKADAPT, 'Stackadapt'),
    ]
    
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default=GOOGLE  # Default to Google
    )

    name = models.CharField(max_length=100)
    product = models.CharField(max_length=255, null=True, blank=True)  # Changed from user_friendly_name to product
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    campaign_type = models.CharField(max_length=10, choices=CAMPAIGN_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    spend = models.DecimalField(max_digits=10, decimal_places=2)
    impressions = models.IntegerField()
    clicks = models.IntegerField()
    ctr = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cpc = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    conversions = models.IntegerField(null=True, blank=True)
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

class Target(models.Model):
    CAMPAIGN_TYPE_CHOICES = [
        ('Video', 'Video'),
        ('Display', 'Display'),
        ('Search', 'Search'),
    ]

    GOOGLE = 'Google'
    STACKADAPT = 'Stackadapt'
    
    CHANNEL_CHOICES = [
        (GOOGLE, 'Google'),
        (STACKADAPT, 'Stackadapt'),
    ]

    product = models.CharField(max_length=255)  # Or ForeignKey if a product model exists
    client = models.ForeignKey(Client, on_delete=models.CASCADE)  # Link to client
    campaign_type = models.CharField(max_length=10, choices=CAMPAIGN_TYPE_CHOICES)  # Add campaign type
    month = models.DateField()  # Store the month and year (ensure it's always the 1st day)
    target_spend = models.DecimalField(max_digits=12, decimal_places=2)
    target_impressions = models.IntegerField()
    target_clicks = models.IntegerField()

    # Add channel field with a default of Google
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=GOOGLE)

    # Calculated fields for CTR and CPC
    @property
    def target_ctr(self):
        """ Calculate CTR: Click-through rate (%) """
        if self.target_impressions > 0:
            return (self.target_clicks / self.target_impressions) * 100
        return 0

    @property
    def target_cpc(self):
        """ Calculate CPC: Cost per click """
        if self.target_clicks > 0:
            return self.target_spend / self.target_clicks
        return 0

    def save(self, *args, **kwargs):
        """ Ensure the month is always saved as the first day of the month """
        if self.month:
            self.month = self.month.replace(day=1)  # Normalize to the first day of the month
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Target for {self.product} ({self.campaign_type}) - {self.month.strftime('%B %Y')} - {self.channel}"

    class Meta:
        """ Ensure that targets are unique per product, campaign type, and month """
        unique_together = ('product', 'month', 'client', 'campaign_type', 'channel')  # Ensure uniqueness for client-product-month-type combo, now including channel
        ordering = ['month', 'product', 'campaign_type']  # Default ordering
