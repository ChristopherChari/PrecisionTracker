import csv
from collections import defaultdict
from decimal import Decimal  # Import Decimal
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.utils.dateparse import parse_date  # Check if you use it, otherwise remove it
from django.db import transaction
from django.http import JsonResponse
from django.template.loader import render_to_string

from .models import Client, Campaign, MonthlyData, Target
from .forms import CampaignForm, CampaignFilterForm, CampaignNameMappingForm, CampaignUploadForm, TargetForm

# Consolidate imports from the same module to reduce redundancy


# Mapping for Campaign Group to Client name
CAMPAIGN_GROUP_TO_CLIENT = {
    "Haliborange": "Haliborange - PCM",
    "BIOGLAN": "Bioglan",
    "Superfoods": "Bioglan Superfoods",
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
    form = None
    existing_target = None
    overwrite_confirmed = request.POST.get('confirm_overwrite', 'false') == 'true'

    if request.method == 'POST':
        client_id = request.POST.get('client')
        product = request.POST.get('product')
        campaign_type = request.POST.get('campaign_type')
        channel = request.POST.get('channel')
        month = request.POST.get('month')

        # Convert month to the first day of the selected month
        month = datetime.strptime(month, '%Y-%m').replace(day=1)

        # Check if a target exists for the current selection
        try:
            existing_target = Target.objects.get(
                client_id=client_id,
                product=product,
                campaign_type=campaign_type,
                channel=channel,
                month=month
            )
        except Target.DoesNotExist:
            existing_target = None

        form = TargetForm(request.POST, instance=existing_target)  # Bind form to existing instance

        if form.is_valid():
            # Only save changes if form is valid
            if existing_target:
                if not overwrite_confirmed:
                    messages.warning(request, 'A target already exists for this selection. Confirm to overwrite.')
                    return render(request, 'CampaignTracker/enter_target.html', {
                        'form': form,
                        'existing_target': existing_target,
                        'confirm_overwrite': True,  # Show confirmation message
                    })
                else:
                    # Save updates to the existing target
                    form.save()
                    messages.success(request, 'Target updated successfully!')
            else:
                # Save a new target
                form.save()
                messages.success(request, 'Target created successfully!')

            return redirect('enter_target')  # Redirect to avoid re-submission
        else:
            messages.error(request, 'There was an error with your submission. Please check the form.')

    else:
        # For GET request, initialize the form
        form = TargetForm()

    # Fetch all clients
    clients = Client.objects.all()

    return render(request, 'CampaignTracker/enter_target.html', {
        'form': form,
        'existing_target': existing_target,
        'clients': clients,
        'confirm_overwrite': False,  # Reset overwrite confirmation
    })


def check_existing_target(request):
    client_id = request.GET.get('client')
    product = request.GET.get('product')
    campaign_type = request.GET.get('campaign_type')
    channel = request.GET.get('channel')
    month = request.GET.get('month')

    if client_id and product and campaign_type and channel and month:
        # Parse the month into a date object
        try:
            month = datetime.strptime(month, '%Y-%m').replace(day=1)
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
        
        # Try to find an existing target
        try:
            target = Target.objects.get(
                client_id=client_id,
                product=product,
                campaign_type=campaign_type,
                channel=channel,
                month=month
            )

            # Return target details in JSON format
            target_data = {
                'client': target.client.name,
                'product': target.product,
                'campaign_type': target.campaign_type,
                'month': target.month.strftime('%B %Y'),
                'target_spend': float(target.target_spend),
                'target_impressions': target.target_impressions,
                'target_clicks': target.target_clicks,
                'channel': target.channel
            }
            return JsonResponse({'target': target_data})

        except Target.DoesNotExist:
            return JsonResponse({'target': None})

    return JsonResponse({'error': 'Missing parameters'}, status=400)

def get_products_for_client(request):
    client_id = request.GET.get('client_id')
    products = []

    if client_id:
        # Fetch distinct products for the selected client
        campaigns = Campaign.objects.filter(client_id=client_id).values_list('product', flat=True).distinct()
        products = list(campaigns)

    return JsonResponse({'products': products})

def get_previous_period_data(client, product, channel, start_date, end_date, period='7days'):
    # Get the previous period's date range
    if period == '7days':
        previous_start_date = start_date - timedelta(days=7)
        previous_end_date = end_date - timedelta(days=7)
    elif period == 'month':
        previous_start_date = (start_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        previous_end_date = start_date - timedelta(days=1)

    # Fetch campaigns for the previous period
    previous_campaigns = Campaign.objects.filter(
        client=client,
        product=product,
        start_date__gte=previous_start_date,
        end_date__lte=previous_end_date,
    )
    
    if channel:
        previous_campaigns = previous_campaigns.filter(channel=channel)

    # Aggregate previous period data
    previous_data = {
        'spend': sum(c.spend for c in previous_campaigns),
        'impressions': sum(c.impressions for c in previous_campaigns),
        'clicks': sum(c.clicks for c in previous_campaigns)
    }

    return previous_data


def filter_campaigns(request):
    clients = Client.objects.all()
    campaigns_by_type = {}
    client_id = request.GET.get('client', request.session.get('selected_client'))
    product = request.GET.get('product', request.session.get('selected_product'))
    selected_channel = request.GET.get('channel', request.session.get('selected_channel'))
    start_date = request.GET.get('start_date', request.session.get('selected_start_date'))
    end_date = request.GET.get('end_date', request.session.get('selected_end_date'))
    comparison_period = request.GET.get('comparison_period','7days')  # Comparison period: 7 days or month
    

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

    # If the client_id is invalid or the client was deleted, reset the session
    if client_id:
        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            # If the client was deleted, clear the session and return to avoid error
            del request.session['selected_client']
            client_id = None  # Reset client_id to avoid further issues

    if client_id and product and start_date and end_date:
        client = get_object_or_404(Client, id=client_id)
        start_date = parse_date(start_date)
        end_date = parse_date(end_date)
        total_days_selected = (end_date - start_date).days + 1

        # Calculate the previous period start and end dates
        if comparison_period == '7days':
            prev_start_date = start_date - timedelta(days=7)
            prev_end_date = end_date - timedelta(days=7)
        else:  # 'month' comparison
            prev_start_date = (start_date - timedelta(days=30)).replace(day=1)
            prev_end_date = prev_start_date + timedelta(days=30) - timedelta(seconds=1)

        campaigns = Campaign.objects.filter(
            client=client,
            product=product,
            start_date__gte=start_date,
            end_date__lte=end_date,
        )
        
        if selected_channel:
            campaigns = campaigns.filter(channel=selected_channel)

        # Fetch previous period campaigns for comparison
        previous_campaigns = Campaign.objects.filter(
            client=client,
            product=product,
            start_date__gte=prev_start_date,
            end_date__lte=prev_end_date,
        )
        
        if selected_channel:
            previous_campaigns = previous_campaigns.filter(channel=selected_channel)

        for campaign in campaigns:
            campaign_type = f"{campaign.channel} {campaign.campaign_type}"

            target = Target.objects.filter(
                client=client,
                product=product,
                campaign_type=campaign.campaign_type,
                month__year=start_date.year,
                month__month=start_date.month,
                channel=campaign.channel
            ).first()

            if target:
                days_in_month = (target.month.replace(month=target.month.month % 12 + 1, day=1) - timedelta(days=1)).day
                proportion_of_month = Decimal(total_days_selected) / Decimal(days_in_month)

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
                    'spend_diff': 0,
                    'impressions_diff': 0,
                    'clicks_diff': 0,
                    'previous_spend': 0,
                    'previous_impressions': 0,
                    'previous_clicks': 0,
                }

            campaigns_by_type[campaign_type]['campaigns'].append(campaign)
            campaigns_by_type[campaign_type]['total_impressions'] += campaign.impressions
            campaigns_by_type[campaign_type]['total_clicks'] += campaign.clicks
            campaigns_by_type[campaign_type]['total_spend'] += campaign.spend

        # Now calculate the previous actuals and compare them
        # Now calculate the previous actuals and compare them
    for campaign_type, data in campaigns_by_type.items():
        # Initialize the previous metrics to 0 to avoid KeyError
        data['previous_spend'] = 0
        data['previous_impressions'] = 0
        data['previous_clicks'] = 0
        data['previous_ctr'] = 0  # Initialize CTR to 0
        data['previous_cpc'] = 0  # Initialize CPC to 0

        # Get the previous period campaigns for this campaign_type
        prev_campaigns = previous_campaigns.filter(campaign_type=campaign_type.split()[1])  # Removing channel prefix
        
        for prev_campaign in prev_campaigns:
            data['previous_spend'] += prev_campaign.spend
            data['previous_impressions'] += prev_campaign.impressions
            data['previous_clicks'] += prev_campaign.clicks

        # Calculate previous CTR and CPC based on the total previous impressions and clicks
        if data['previous_impressions'] > 0:
            data['previous_ctr'] = (data['previous_clicks'] / data['previous_impressions']) * 100

        if data['previous_clicks'] > 0:
            data['previous_cpc'] = data['previous_spend'] / data['previous_clicks']

        # Calculate percentage differences with previous actuals
        if data['previous_spend'] > 0:
            data['spend_diff'] = ((data['total_spend'] - data['previous_spend']) / data['previous_spend']) * 100
            data['spend_diffnum'] = data['total_spend'] - data['previous_spend']

        if data['previous_impressions'] > 0:
            data['impressions_diff'] = ((data['total_impressions'] - data['previous_impressions']) / data['previous_impressions']) * 100
            data['impressions_diffnum'] = data['total_impressions'] - data['previous_impressions']

        if data['previous_clicks'] > 0:
            data['clicks_diff'] = ((data['total_clicks'] - data['previous_clicks']) / data['previous_clicks']) * 100
            data['clicks_diffnum'] = data['total_clicks'] - data['previous_clicks']

        # Calculate CTR and CPC for the current period
        if data['total_impressions'] > 0:
            data['total_ctr'] = (data['total_clicks'] / data['total_impressions']) * 100
        else:
            data['total_ctr'] = 0  # No impressions, so CTR is 0

        if data['total_clicks'] > 0:
            data['total_cpc'] = data['total_spend'] / data['total_clicks']
        else:
            data['total_cpc'] = 0  # No clicks, so CPC is 0

        # Calculate CTR percentage difference and absolute difference
        if data['previous_ctr'] > 0:
            data['ctr_diff'] = ((data['total_ctr'] - data['previous_ctr']) / data['previous_ctr']) * 100
            data['ctr_diffnum'] = data['total_ctr'] - data['previous_ctr']

        # Calculate CPC percentage difference and absolute difference
        if data['previous_cpc'] > 0:
            data['cpc_diff'] = ((data['total_cpc'] - data['previous_cpc']) / data['previous_cpc']) * 100
            data['cpc_diffnum'] = data['total_cpc'] - data['previous_cpc']

   
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        rendered_campaigns = render_to_string('CampaignTracker/campaign_list.html', {
            'campaigns_by_type': campaigns_by_type,
        })
        rendered_kpis = render_to_string('CampaignTracker/kpi_cards.html', {
            'campaigns_by_type': campaigns_by_type,
            'comparison_period': comparison_period,  # Pass comparison period
        })
        return JsonResponse({'html': rendered_campaigns, 'kpi_html': rendered_kpis})

    

    return render(request, 'CampaignTracker/filter_campaigns.html', {
        'clients': clients,
        'campaigns_by_type': campaigns_by_type,
        'selected_client': client_id,
        'selected_product': product,
        'selected_channel': selected_channel,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
        'comparison_period': comparison_period,
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

def upload_campaign_report(request):
    campaigns = []
    combined_data = []
    filtered_campaigns = []
    campaign_name_to_product = {}

    # Get the list of all clients to populate the client dropdown
    clients = Client.objects.all()

    client_id = request.POST.get('client')
    selected_channel = request.POST.get('channel')

    # Fetch existing campaign name to product mappings
    existing_mappings = Campaign.objects.values('name', 'product').distinct()

    # Create a dictionary for quick lookup of campaign-to-product mappings
    campaign_name_to_product = {mapping['name']: mapping['product'] for mapping in existing_mappings if mapping['product']}

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
                        client = get_or_create_client_from_campaign_group(row['Account name'])

                        # Automatically map the product if it already exists for the campaign name
                        product_name = campaign_name_to_product.get(row['Campaign'], '')

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
                                'product': product_name,  # Automatically map product if it exists
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
                        campaign_date = datetime.strptime(row['Date'], '%d/%m/%').date()

                        # Retrieve client from the Campaign Group column
                        client = get_or_create_client_from_campaign_group(row['Campaign Group'])

                        # Automatically map the product if it already exists for the campaign name
                        product_name = campaign_name_to_product.get(row['Campaign'], '')

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
                                'product': product_name,  # Automatically map product if it exists
                            }
                        )
                        combined_data.append(campaign)

                    except Exception as e:
                        messages.error(request, f"Error processing row: {row['Campaign']} - {str(e)}")
                        continue

        # Remove duplicates from combined_data by campaign name
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
