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

class CampaignUploadForm(forms.Form):
    # Other fields you may have, such as for file upload
    campaign_file = forms.FileField(label='Upload Campaign File')

    # Add channel field as a dropdown
    CHANNEL_CHOICES = [
        ( 'Google'),
        ( 'Stackadapt'),
    ]
    channel = forms.ChoiceField(choices=CHANNEL_CHOICES, label="Channel")

class TargetForm(forms.ModelForm):
    class Meta:
        model = Target
        fields = ['client', 'product', 'campaign_type', 'month', 'target_spend', 'target_impressions', 'target_clicks', 'channel']

        widgets = {
            'month': forms.DateInput(attrs={'type': 'month'}, format='%Y-%m'),  # Ensure the format matches 'YYYY-MM'
            'channel': forms.Select(choices=Target.CHANNEL_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['month'].input_formats = ['%Y-%m']
        # Set optional fields
        self.fields['target_spend'].required = True
        self.fields['target_impressions'].required = True
        self.fields['target_clicks'].required = True

        # Dynamically update the product field based on the selected client
        if 'client' in self.data:
            try:
                client_id = int(self.data.get('client'))
                products = Target.objects.filter(client_id=client_id).values_list('product', flat=True).distinct()
                self.fields['product'].widget = forms.Select(choices=[('', '-- Select Product --')] + [(p, p) for p in products])
            except (ValueError, TypeError):
                self.fields['product'].widget = forms.Select(choices=[('', '-- Select Product --')])
        elif self.instance.pk:
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
