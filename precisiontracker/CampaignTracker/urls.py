from django.urls import path
from . import views
from .views import filter_campaigns,  map_campaign_name, enter_targets


urlpatterns = [
    path('upload/', views.upload_campaign_report, name='upload_campaign_report'),
    path('', filter_campaigns, name='home'),
    path('get-products/', views.get_products_for_client, name='get_products_for_client'),
    path('enter-target/', enter_targets, name='enter_target'),
    path('map-campaign-name/', map_campaign_name, name='map_campaign_name')
    # Add other URL patterns as needed
]
