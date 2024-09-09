import csv
from collections import defaultdict
from turtle import home
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Client, Campaign, MonthlyData
from django.core.files.storage import FileSystemStorage
from django.utils.dateparse import parse_date
from .forms import CampaignForm, CampaignFilterForm

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


def filter_campaigns(request):
    clients = Client.objects.all()
    campaigns_by_type = {}
    client_id = request.GET.get('client', request.session.get('selected_client'))
    product = request.GET.get('product', request.session.get('selected_product'))
    start_date = request.GET.get('start_date', request.session.get('selected_start_date'))
    end_date = request.GET.get('end_date', request.session.get('selected_end_date'))

    if client_id:
        request.session['selected_client'] = client_id
    if product:
        request.session['selected_product'] = product
    if start_date:
        request.session['selected_start_date'] = start_date
    if end_date:
        request.session['selected_end_date'] = end_date

    if client_id and product and start_date and end_date:
        client = get_object_or_404(Client, id=client_id)
        start_date = parse_date(start_date)
        end_date = parse_date(end_date)
        total_days_selected = (end_date - start_date).days + 1

        campaigns = Campaign.objects.filter(client=client, product=product, start_date__gte=start_date, end_date__lte=end_date)

        for campaign in campaigns:
            campaign_type = campaign.campaign_type

            # Fetch the specific target for this campaign type
            target = Target.objects.filter(client=client, product=product, campaign_type=campaign_type, month__year=start_date.year, month__month=start_date.month).first()

            if target:
                days_in_month = (target.month.replace(month=target.month.month % 12 + 1, day=1) - timedelta(days=1)).day
                proportion_of_month = Decimal(total_days_selected) / Decimal(days_in_month)

                # Calculate the dynamic targets
                target_spend = target.target_spend * proportion_of_month
                target_impressions = target.target_impressions * proportion_of_month
                target_clicks = target.target_clicks * proportion_of_month

                # Calculate target CPC and CTR (not stored in the database)
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
                    'target_ctr': target_ctr,  # Adding target CTR
                    'target_cpc': target_cpc,  # Adding target CPC
                }

            campaigns_by_type[campaign_type]['campaigns'].append(campaign)
            campaigns_by_type[campaign_type]['total_impressions'] += campaign.impressions
            campaigns_by_type[campaign_type]['total_clicks'] += campaign.clicks
            campaigns_by_type[campaign_type]['total_spend'] += campaign.spend

        for campaign_type, data in campaigns_by_type.items():
            if data['total_clicks'] > 0:
                data['total_ctr'] = (data['total_clicks'] / data['total_impressions']) * 100 if data['total_impressions'] > 0 else 0
                data['total_cpc'] = data['total_spend'] / data['total_clicks'] if data['total_clicks'] > 0 else 0

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
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
        'selected_product': product,
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

    return render(request, 'CampaignTracker/name_mapping.html', {
        'combined_data': campaigns,
    })

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

        # Parse CSV file
        with open(fs.path(filename), mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    # Ensure required fields are available in the CSV row
                    if 'Campaign' not in row or 'Campaign type' not in row or 'Day' not in row:
                        messages.error(request, f"Missing required data in row: {row}")
                        continue

                    # Convert numerical fields
                    impressions = int(str(row.get('Impr.', 0)).replace(',', ''))  # Convert impressions to integer
                    clicks = int(str(row.get('Clicks', 0)).replace(',', ''))      # Convert clicks to integer
                    spend = float(str(row.get('Cost', 0)).replace(',', ''))       # Convert spend to float
                    budget = float(str(row.get('Budget', 0)).replace(',', ''))    # Convert budget to float

                    # Parse the date from the 'Day' column
                    campaign_date = datetime.strptime(row['Day'], '%d/%m/%Y').date()

                    # Get or create campaign based on name and date
                    client = get_object_or_404(Client, id=client_id)
                    campaign, created = Campaign.objects.get_or_create(
                        name=row['Campaign'],
                        start_date=campaign_date,  # Use date from the CSV file
                        end_date=campaign_date,    # Assuming this is a daily record
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

                    # Check if a product mapping exists for this campaign name
                    if campaign.product:
                        campaign_name_to_product[campaign.name] = campaign.product

                    # Add campaign to combined data (for name mapping)
                    combined_data.append(campaign)

                except ValueError as e:
                    # Handle any errors that occur while processing the CSV row
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