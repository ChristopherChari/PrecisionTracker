from django import forms
from .models import Campaign, Client, Target

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
    product = forms.CharField(max_length=255)

from datetime import datetime

class TargetForm(forms.ModelForm):
    class Meta:
        model = Target
        fields = ['client', 'product', 'campaign_type', 'month', 'target_spend', 'target_impressions', 'target_clicks']
        widgets = {
            'month': forms.DateInput(attrs={'type': 'month'}, format='%Y-%m')  # Ensure the format matches 'YYYY-MM'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set input formats explicitly
        self.fields['month'].input_formats = ['%Y-%m']

        # Dynamically update the product field based on the selected client
        if 'client' in self.data:
            try:
                client_id = int(self.data.get('client'))
                # Get products linked to the selected client
                products = Target.objects.filter(client_id=client_id).values_list('product', flat=True).distinct()
                self.fields['product'].widget = forms.Select(choices=[('', '-- Select Product --')] + [(p, p) for p in products])
            except (ValueError, TypeError):
                self.fields['product'].widget = forms.Select(choices=[('', '-- Select Product --')])
        elif self.instance.pk:
            # If editing an existing entry, show the products for the associated client
            client_id = self.instance.client_id
            products = Target.objects.filter(client_id=client_id).values_list('product', flat=True).distinct()
            self.fields['product'].widget = forms.Select(choices=[('', '-- Select Product --')] + [(p, p) for p in products])
        else:
            self.fields['product'].widget = forms.Select(choices=[('', '-- Select Product --')])

    def clean_month(self):
        month = self.cleaned_data['month']
        if month:
            # Ensure the date is set to the first day of the selected month
            return month.replace(day=1)
        return month