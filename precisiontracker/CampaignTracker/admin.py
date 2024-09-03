from django.contrib import admin
from .models import Client, Channel, Campaign, MonthlyData

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name',)

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'created_at', 'updated_at')
    search_fields = ('name', 'client__name')

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'campaign_type', 'client', 'start_date', 'end_date', 'budget', 'spend')
    list_filter = ('campaign_type', 'client', 'start_date', 'end_date')
    search_fields = ('name', 'client__name')

@admin.register(MonthlyData)
class MonthlyDataAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'month', 'budget', 'spend', 'impressions', 'clicks', 'conversions')
    list_filter = ('campaign', 'month')
    search_fields = ('campaign__name',)
