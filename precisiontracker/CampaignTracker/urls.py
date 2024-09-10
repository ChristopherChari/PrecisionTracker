from django.urls import path
from . import views
from .views import filter_campaigns,  name_mapping , enter_targets, name_mapping_ajax


urlpatterns = [
    path('upload/', views.upload_campaign_report, name='upload_campaign_report'),
    path('', filter_campaigns, name='home'),
    path('get-products/', views.get_products_for_client, name='get_products_for_client'),
    path('enter-target/', enter_targets, name='enter_target'),
    path('map-campaign-name/', name_mapping, name='name_mapping'),
    path('name-mapping/', name_mapping, name='name_mapping'),
    path('name-mapping/ajax/', name_mapping_ajax, name='name_mapping_ajax'),
    # Add other URL patterns as needed
]
