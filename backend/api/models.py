from django.db import models

class Campaign(models.Model):
    campaign_id = models.CharField(max_length=100)
    campaign_name = models.CharField(max_length=255)
    cluster = models.IntegerField()
    recommendation = models.TextField()

    cost = models.FloatField()
    revenue = models.FloatField()
    profit = models.FloatField()
    clicks = models.IntegerField()
    conversions = models.IntegerField()
    conversion_rate = models.FloatField()
    roi = models.FloatField()
    cpc = models.FloatField()
    profit_margin = models.FloatField()

    timestamp = models.DateTimeField()
    state = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.campaign_name} (Cluster {self.cluster})"



# class CampaignAd(models.Model):
#     fb_campaign_id = models.IntegerField()
#     fb_adset_id = models.BigIntegerField()  # Changed to BigIntegerField for long sub_id_2 values
#     fb_campaign_name = models.CharField(max_length=255)
#     cost = models.FloatField()
#     revenue = models.FloatField()
#     profit = models.FloatField()
#     clicks = models.IntegerField()
#     campaign_unique_clicks = models.IntegerField()
#     conversions = models.IntegerField()
#     roi_confirmed = models.FloatField()
#     timestamp = models.DateTimeField()
#     lp_clicks = models.IntegerField()
#     cr = models.FloatField()
#     lp_ctr = models.FloatField()
#     sub_id_2 = models.CharField(max_length=255)
#     sub_id_3 = models.CharField(max_length=255)
#     sub_id_5 = models.CharField(max_length=255)
#     sub_id_6 = models.CharField(max_length=255)
#     log_revenue = models.FloatField(default=0)
#     log_cr = models.FloatField(default=0)
#     cluster = models.IntegerField()
#     recommendation = models.CharField(max_length=255)
#     urgency = models.CharField(max_length=50, blank=True, null=True)
#     priority = models.CharField(max_length=50, blank=True, null=True)
#     reason = models.TextField(blank=True, null=True)  # <-- added this line
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         indexes = [
#             models.Index(fields=['fb_adset_id']),
#             models.Index(fields=['sub_id_2']),
#         ]
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"{self.fb_campaign_name} (AdSet ID: {self.fb_adset_id}) - {self.recommendation}"


class CampaignAdSet(models.Model):
    sub_id_6 = models.CharField(max_length=255, blank=True, null=True)
    sub_id_5 = models.CharField(max_length=255, blank=True, null=True)
    sub_id_2 = models.CharField(max_length=255, blank=True, null=True)
    sub_id_3 = models.CharField(max_length=255, blank=True, null=True)
    day = models.DateField(blank=True, null=True)

    clicks = models.IntegerField(default=0)
    lp_clicks = models.IntegerField(default=0)
    lp_ctr = models.FloatField(default=0.0)
    cr = models.FloatField(default=0.0)

    cost = models.FloatField(default=0.0)
    campaign_unique_clicks = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    roi_confirmed = models.FloatField(default=0.0)
    revenue = models.FloatField(default=0.0)
    profit = models.FloatField(default=0.0)
    revenue_to_cost_ratio = models.FloatField(default=0.0)
    conversion_rate = models.FloatField(default=0.0)
    profit_margin = models.FloatField(default=0.0)
    cluster = models.IntegerField(default=-1)

    recommendation = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    priority = models.IntegerField(default=0)
    urgent = models.BooleanField(default=False)
    action_needed = models.BooleanField(default=False)
    potential_impact = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AdSet {self.sub_id_2} | Day: {self.day}"