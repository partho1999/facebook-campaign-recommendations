from django.urls import path
from .views import PredictCampaignsView, PredictionsView

urlpatterns = [
    path('prediction-run/', PredictCampaignsView.as_view(), name='predict-campaigns'),
    path('predictions/', PredictionsView.as_view(), name='predictions'),
]