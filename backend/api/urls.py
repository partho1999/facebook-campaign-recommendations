from django.urls import path
from .views import PredictCampaignsView, PredictTimeRangeView, PredictCampaignsUpdateView

urlpatterns = [
    path('prediction-run/', PredictCampaignsView.as_view(), name='predict-campaigns'),
    path('predict-time-range/', PredictTimeRangeView.as_view(), name='predict-time-range'),
    path('predictions-combine/', PredictCampaignsUpdateView.as_view(), name='predictions-combine'),
]