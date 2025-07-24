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