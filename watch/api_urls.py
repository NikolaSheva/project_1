# watch/api_urls.py
from django.urls import path
import watch.api_endpoint as api_endpoint

app_name = 'watch_api'

urlpatterns = [
    path('get-unsent/', api_endpoint.get_unsent_products, name='get_unsent'),
    path('mark-sent/', api_endpoint.mark_as_sent, name='mark_sent'),
    path('health/', api_endpoint.health_check, name='health'),
]