from django import forms
from .models import Campaign, Client

class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['budget', 'spend', 'impressions', 'clicks', 'ctr', 'cpc']

class CampaignFilterForm(forms.Form):
    client = forms.ModelChoiceField(queryset=Client.objects.all(), required=True)
    start_date = forms.DateField(required=True)
    end_date = forms.DateField(required=True)


class CampaignNameMappingForm(forms.Form):
    campaign_id = forms.IntegerField(widget=forms.HiddenInput())
    csv_name = forms.CharField(max_length=255, disabled=True)
    user_friendly_name = forms.CharField(max_length=255)