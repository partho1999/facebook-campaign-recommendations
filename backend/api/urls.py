from django.urls import path
from .views import PredictCampaignsView, PredictTimeRangeView #PredictionsView

urlpatterns = [
    path('prediction-run/', PredictCampaignsView.as_view(), name='predict-campaigns'),
    path('predict-time-range/', PredictTimeRangeView.as_view(), name='predict-time-range'),
    # path('predictions/', PredictionsView.as_view(), name='predictions'),
]