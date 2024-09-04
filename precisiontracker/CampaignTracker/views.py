import csv
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Client, Channel, Campaign, MonthlyData
from django.core.files.storage import FileSystemStorage
from django.utils.dateparse import parse_date
from .forms import CampaignForm, CampaignFilterForm

from django.shortcuts import render, get_object_or_404
from .models import Client, Campaign
from .forms import CampaignNameMappingForm

from django.http import JsonResponse
from django.template.loader import render_to_string

def filter_campaigns(request):
    clients = Client.objects.all()
    campaigns_by_type = {}
    client_id = request.GET.get('client', request.session.get('selected_client'))
    start_date = request.GET.get('start_date', request.session.get('selected_start_date'))
    end_date = request.GET.get('end_date', request.session.get('selected_end_date'))

    if client_id:
        request.session['selected_client'] = client_id
    if start_date:
        request.session['selected_start_date'] = start_date
    if end_date:
        request.session['selected_end_date'] = end_date

    if client_id and start_date and end_date:
        client = get_object_or_404(Client, id=client_id)
        campaigns = Campaign.objects.filter(client=client, start_date__gte=start_date, end_date__lte=end_date)

        for campaign in campaigns:
            campaign_type = campaign.campaign_type
            if campaign_type not in campaigns_by_type:
                campaigns_by_type[campaign_type] = {
                    'campaigns': [],
                    'total_impressions': 0,
                    'total_clicks': 0,
                    'total_spend': 0,
                    'total_ctr': 0,
                    'total_cpc': 0,
                }
            campaigns_by_type[campaign_type]['campaigns'].append(campaign)
            campaigns_by_type[campaign_type]['total_impressions'] += campaign.impressions
            campaigns_by_type[campaign_type]['total_clicks'] += campaign.clicks
            campaigns_by_type[campaign_type]['total_spend'] += campaign.spend
            campaigns_by_type[campaign_type]['total_ctr'] += campaign.ctr
            campaigns_by_type[campaign_type]['total_cpc'] += campaign.cpc

        # Calculate average CTR and CPC for each campaign type
        for campaign_type, data in campaigns_by_type.items():
            if data['total_clicks'] > 0:
                data['total_ctr'] = (data['total_clicks'] / data['total_impressions']) * 100 if data['total_impressions'] > 0 else 0
                data['total_cpc'] = data['total_spend'] / data['total_clicks'] if data['total_clicks'] > 0 else 0

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':  # Check if request is AJAX
        rendered_campaigns = render_to_string('CampaignTracker/campaign_list.html', {
            'campaigns_by_type': campaigns_by_type,
        })
        return JsonResponse({
            'html': rendered_campaigns,
        })

    return render(request, 'CampaignTracker/filter_campaigns.html', {
        'clients': clients,
        'campaigns_by_type': campaigns_by_type,
        'selected_client': client_id,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
    })


from django.shortcuts import redirect, get_object_or_404
from .models import Campaign

def map_campaign_name(request):
    if request.method == 'POST':
        campaign_id = request.POST.get('campaign_id')
        product = request.POST.get('product')

        campaign = get_object_or_404(Campaign, id=campaign_id)
        campaign.product = product
        campaign.save()

        return redirect('home')  # Redirect back to the home page after saving

def upload_campaign_report(request):
    campaigns = []
    combined_data = []
    filtered_campaigns = []

    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')
    client_id = request.POST.get('client')

    if client_id and start_date and end_date:
        client = get_object_or_404(Client, id=client_id)
        filtered_campaigns = Campaign.objects.filter(
            client=client,
            start_date__gte=start_date,
            end_date__lte=end_date
        )

    if request.method == 'POST' and request.FILES.get('campaign_file'):
        campaign_file = request.FILES['campaign_file']
        fs = FileSystemStorage()
        filename = fs.save(campaign_file.name, campaign_file)
        uploaded_file_url = fs.url(filename)

        # Parse CSV file
        with open(fs.path(filename), mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                campaign_data = {
                    'csv_name': row['Campaign'],
                    'budget': row['Budget'],
                    'impressions': int(row['Impr.'].replace(',', '')),
                    'clicks': int(row['Clicks'].replace(',', '')),
                    'spend': float(row['Cost']),
                    'campaign_type': row['Campaign type']
                }
                campaigns.append(campaign_data)

                # Prepare the form for each campaign
                mapping_form = CampaignNameMappingForm(initial={
                    'csv_name': campaign_data['csv_name'],
                })

                combined_data.append((campaign_data, mapping_form))

    elif request.method == 'POST' and request.POST.get('mapping_submitted'):
        # Handle the name mapping submission for both new and past campaigns
        for key in request.POST:
            if key.startswith('product_'):
                campaign_index = int(key.split('_')[-1])
                csv_name = request.POST.get(f'csv_name_{campaign_index}')
                product = request.POST.get(key)
                
                # Save the mapped name to the Campaign model or update it
                campaign = Campaign.objects.get(name=csv_name)
                campaign.product = product
                campaign.save()

    return render(request, 'CampaignTracker/upload_campaign_report.html', {
        'combined_data': combined_data,
        'filtered_campaigns': filtered_campaigns,
        'start_date': start_date,
        'end_date': end_date,
        'client_id': client_id,
    })