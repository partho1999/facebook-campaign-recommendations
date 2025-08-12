from django.urls import path
from .views import (
    PredictCampaignsView, 
    PredictTimeRangeView, 
    PredictCampaignsUpdateView,
    PredictCampaignsDailyView,
    PredictDateRangeView
) 

urlpatterns = [
    path('prediction-run/', PredictCampaignsView.as_view(), name='predict-campaigns'),
    path('predict-time-range/', PredictTimeRangeView.as_view(), name='predict-time-range'),
    path('predictions-combine/', PredictCampaignsUpdateView.as_view(), name='predictions-combine'),
    path('prediction-daily/', PredictCampaignsDailyView.as_view(), name='daily-predict-campaigns'),
    path('predict-date-range/', PredictDateRangeView.as_view(), name='predict-date-range'),
]