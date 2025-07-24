from rest_framework import serializers
from .models import Campaign

class CampaignSerializer(serializers.ModelSerializer):
    metrics = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            'id', 'campaign_id', 'campaign_name', 'cluster',
            'recommendation', 'metrics', 'timestamp', 'state'
        ]

    def get_metrics(self, obj):
        return {
            'cost': obj.cost,
            'revenue': obj.revenue,
            'profit': obj.profit,
            'clicks': obj.clicks,
            'conversions': obj.conversions,
            'conversion_rate': obj.conversion_rate,
            'roi': obj.roi,
            'cpc': obj.cpc,
            'profit_margin': obj.profit_margin,
        }