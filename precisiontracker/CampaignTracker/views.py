import csv
from collections import defaultdict
from turtle import home
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Client, Campaign, MonthlyData
from django.core.files.storage import FileSystemStorage
from django.utils.dateparse import parse_date
from .forms import CampaignForm, CampaignFilterForm
from django.db import transaction

from datetime import timedelta
from decimal import Decimal  # Import Decimal

from django.shortcuts import render, get_object_or_404
from .models import Client, Campaign
from .forms import CampaignNameMappingForm, CampaignUploadForm

from django.http import JsonResponse
from django.template.loader import render_to_string


from django.shortcuts import render, redirect
from .forms import  TargetForm
from .models import Target, Client
import logging
from datetime import datetime

# Mapping for Campaign Group to Client name
CAMPAIGN_GROUP_TO_CLIENT = {
    "Haliborange": "Haliborange - PCM",
    "BIOGLAN": "Bioglan",
    "PROMENSIL" : "Promensil",
    "Skin Doctors" : "Skin Doctors - PCM"
}

def get_or_create_client_from_campaign_group(campaign_group):
    """
    Map the campaign group to a client name, and get or create the Client object.
    """
    client_name = CAMPAIGN_GROUP_TO_CLIENT.get(campaign_group, campaign_group)  # Default to the campaign group itself if not in the map
    client, created = Client.objects.get_or_create(name=client_name)
    return client

def enter_targets(request):
    if request.method == 'POST':
        form = TargetForm(request.POST)
        if form.is_valid():
            # Print the cleaned data before saving (including the cleaned month)
            print(f"Cleaned form data: {form.cleaned_data}")
            
            form.save()
            messages.success(request, 'Target saved successfully!')
            return redirect('enter_target')  # Redirect to the same page after successful save
        else:
            # Debugging: print form errors to the terminal
            print("Form errors:", form.errors)
            messages.error(request, 'There was an error with your submission. Please check the form.')
    else:
        form = TargetForm()

    return render(request, 'CampaignTracker/enter_target.html', {'form': form})

def get_products_for_client(request):
    client_id = request.GET.get('client_id')
    products = []

    if client_id:
        # Fetch distinct products for the selected client
        campaigns = Campaign.objects.filter(client_id=client_id).values_list('product', flat=True).distinct()
        products = list(campaigns)

    return JsonResponse({'products': products})


from django.shortcuts import render
from django.template.loader import render_to_string
from django.http import JsonResponse

def filter_campaigns(request):
    clients = Client.objects.all()
    campaigns_by_type = {}
    client_id = request.GET.get('client', request.session.get('selected_client'))
    product = request.GET.get('product', request.session.get('selected_product'))
    selected_channel = request.GET.get('channel', request.session.get('selected_channel'))
    start_date = request.GET.get('start_date', request.session.get('selected_start_date'))
    end_date = request.GET.get('end_date', request.session.get('selected_end_date'))

    # Store session data
    if client_id:
        request.session['selected_client'] = client_id
    if product:
        request.session['selected_product'] = product
    if selected_channel:
        request.session['selected_channel'] = selected_channel
    if start_date:
        request.session['selected_start_date'] = start_date
    if end_date:
        request.session['selected_end_date'] = end_date

    # Check for client, product, start_date, end_date, and channel to filter campaigns
    if client_id and product and start_date and end_date:
        client = get_object_or_404(Client, id=client_id)
        start_date = parse_date(start_date)
        end_date = parse_date(end_date)
        total_days_selected = (end_date - start_date).days + 1

        # Fetch campaigns based on the selected filters (including channel)
        campaigns = Campaign.objects.filter(
            client=client,
            product=product,
            start_date__gte=start_date,
            end_date__lte=end_date,
        )
        
        # If a channel is selected, filter by it
        if selected_channel:
            campaigns = campaigns.filter(channel=selected_channel)

        for campaign in campaigns:
            campaign_type = f"{campaign.channel} {campaign.campaign_type}"  # Prefix campaign type with channel

            # Fetch the target for this campaign type and channel
            target = Target.objects.filter(
                client=client,
                product=product,
                campaign_type=campaign.campaign_type,
                month__year=start_date.year,
                month__month=start_date.month,
                channel=campaign.channel  # Ensure we're fetching the target for the right channel
            ).first()

            if target:
                days_in_month = (target.month.replace(month=target.month.month % 12 + 1, day=1) - timedelta(days=1)).day
                proportion_of_month = Decimal(total_days_selected) / Decimal(days_in_month)

                # Calculate dynamic targets
                target_spend = target.target_spend * proportion_of_month
                target_impressions = target.target_impressions * proportion_of_month
                target_clicks = target.target_clicks * proportion_of_month
                target_ctr = (target_clicks / target_impressions) * 100 if target_impressions > 0 else 0
                target_cpc = target_spend / target_clicks if target_clicks > 0 else 0
            else:
                target_spend = target_impressions = target_clicks = 0
                target_ctr = target_cpc = 0

            if campaign_type not in campaigns_by_type:
                campaigns_by_type[campaign_type] = {
                    'campaigns': [],
                    'total_impressions': 0,
                    'total_clicks': 0,
                    'total_spend': 0,
                    'total_ctr': 0,
                    'total_cpc': 0,
                    'target_spend': target_spend,
                    'target_impressions': target_impressions,
                    'target_clicks': target_clicks,
                    'target_ctr': target_ctr,
                    'target_cpc': target_cpc,
                }

            campaigns_by_type[campaign_type]['campaigns'].append(campaign)
            campaigns_by_type[campaign_type]['total_impressions'] += campaign.impressions
            campaigns_by_type[campaign_type]['total_clicks'] += campaign.clicks
            campaigns_by_type[campaign_type]['total_spend'] += campaign.spend

        for campaign_type, data in campaigns_by_type.items():
            if data['total_clicks'] > 0:
                data['total_ctr'] = (data['total_clicks'] / data['total_impressions']) * 100 if data['total_impressions'] > 0 else 0
                data['total_cpc'] = data['total_spend'] / data['total_clicks'] if data['total_clicks'] > 0 else 0

    # Handle AJAX request
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        rendered_campaigns = render_to_string('CampaignTracker/campaign_list.html', {
            'campaigns_by_type': campaigns_by_type,
        })
        return JsonResponse({'html': rendered_campaigns})

    # Handle full-page load
    return render(request, 'CampaignTracker/filter_campaigns.html', {
        'clients': clients,
        'campaigns_by_type': campaigns_by_type,
        'selected_client': client_id,
        'selected_product': product,
        'selected_channel': selected_channel,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
    })


def name_mapping(request):
    if request.method == 'POST':
        # Process the name mapping form submission
        for key in request.POST:
            if key.startswith('product_'):
                campaign_name = request.POST.get(f'csv_name_{key.split("_")[-1]}')
                product_name = request.POST.get(key)

                # Update all campaigns with the same name
                Campaign.objects.filter(name=campaign_name).update(product=product_name)
                messages.success(request, f"Product '{product_name}' assigned to all campaigns with the name '{campaign_name}'.")

    # Fetch unique campaign names (remove duplicates)
    campaigns = Campaign.objects.values('name', 'product').distinct()

    # Fetch clients for the dropdown
    clients = Client.objects.all()

    return render(request, 'CampaignTracker/name_mapping.html', {
        'combined_data': campaigns,
        'clients': clients,
    })

def name_mapping_ajax(request):
    client_id = request.GET.get('client')
    channel = request.GET.get('channel')

    # Filter campaigns based on client and channel
    campaigns = Campaign.objects.values('name', 'product').distinct()
    if client_id:
        campaigns = campaigns.filter(client_id=client_id)
    if channel:
        campaigns = campaigns.filter(channel=channel)

    # Render the filtered data into the table
    rendered_table = render_to_string('CampaignTracker/name_mapping_table.html', {
        'combined_data': campaigns,
    })
    return JsonResponse({'html': rendered_table})
# Initialize logger
logger = logging.getLogger(__name__)

from django.contrib import messages

def upload_campaign_report(request):
    campaigns = []
    combined_data = []
    filtered_campaigns = []
    campaign_name_to_product = {}

    # Get the list of all clients to populate the client dropdown
    clients = Client.objects.all()

    client_id = request.POST.get('client')
    selected_channel = request.POST.get('channel')

    # Handle CSV file upload
    if request.method == 'POST' and request.FILES.get('campaign_file'):
        campaign_file = request.FILES['campaign_file']
        fs = FileSystemStorage()
        filename = fs.save(campaign_file.name, campaign_file)
        uploaded_file_url = fs.url(filename)

        # Parse CSV file based on the selected channel
        with open(fs.path(filename), mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)

            # Handle different file structure for Google vs. Stackadapt
            if selected_channel == 'Google':
                # Google processing logic
                for row in reader:
                    try:
                        impressions = int(str(row.get('Impr.', 0)).replace(',', ''))  # Convert impressions to integer
                        clicks = int(str(row.get('Clicks', 0)).replace(',', ''))
                        spend = float(str(row.get('Cost', 0)).replace(',', ''))
                        budget = float(str(row.get('Budget', 0)).replace(',', ''))
                        campaign_date = datetime.strptime(row['Day'], '%d/%m/%Y').date()

                        # Retrieve client from the Campaign Group column
                        client = get_or_create_client_from_campaign_group(row['Campaign Group'])

                        # Process campaign data
                        campaign, created = Campaign.objects.get_or_create(
                            name=row['Campaign'],
                            start_date=campaign_date,
                            end_date=campaign_date,
                            client=client,
                            defaults={
                                'campaign_type': row['Campaign type'],
                                'budget': budget,
                                'spend': spend,
                                'impressions': impressions,
                                'clicks': clicks,
                                'channel': selected_channel,
                            }
                        )
                        combined_data.append(campaign)

                    except Exception as e:
                        messages.error(request, f"Error processing row: {row['Campaign']} - {str(e)}")
                        continue

            elif selected_channel == 'Stackadapt':
                # Stackadapt-specific processing logic
                for row in reader:
                    try:
                        impressions = int(str(row.get('Impressions', 0)).replace(',', ''))
                        clicks = int(str(row.get('Clicks', 0)).replace(',', ''))
                        spend = float(str(row.get('Media Cost', 0)).replace(',', '').replace('£', ''))
                        budget = float(str(row.get('Budget', 0)).replace(',', ''))
                        campaign_date = datetime.strptime(row['Date'], '%Y-%m-%d').date()

                        # Retrieve client from the Campaign Group column
                        client = get_or_create_client_from_campaign_group(row['Campaign Group'])

                        # Process campaign data
                        campaign, created = Campaign.objects.get_or_create(
                            name=row['Campaign'],
                            start_date=campaign_date,
                            end_date=campaign_date,
                            client=client,
                            defaults={
                                'campaign_type': row['Channel Type'],
                                'budget': budget,
                                'spend': spend,
                                'impressions': impressions,
                                'clicks': clicks,
                                'channel': selected_channel,
                            }
                        )
                        combined_data.append(campaign)

                    except Exception as e:
                        messages.error(request, f"Error processing row: {row['Campaign']} - {str(e)}")
                        continue

        # Remove duplicates from combined_data
        unique_campaign_names = {c.name: c for c in combined_data}.values()
        combined_data = list(unique_campaign_names)

    # Handle name mapping update
    elif request.method == 'POST' and request.POST.get('mapping_submitted'):
        for key in request.POST:
            if key.startswith('product_'):
                csv_name = request.POST.get(f'csv_name_{key.split("_")[1]}')
                product_name = request.POST.get(key)

                # Update all campaigns with the same name
                campaigns_with_same_name = Campaign.objects.filter(name=csv_name)
                campaigns_with_same_name.update(product=product_name)
                messages.success(request, f"Product '{product_name}' assigned to all campaigns named '{csv_name}'.")

    # Pass the context data to the template for rendering
    return render(request, 'CampaignTracker/upload_campaign_report.html', {
        'clients': clients,
        'combined_data': combined_data,
        'filtered_campaigns': filtered_campaigns,
        'client_id': client_id,
    })