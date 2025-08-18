from django.contrib import admin
from .models import Campaign, CampaignAdSet
# Register your models here.


admin.site.register(Campaign)

admin.site.register(CampaignAdSet)


admin.site.site_header = "Ads Recomendations Admin"
admin.site.site_title = "My Custom Admin Portal"
admin.site.index_title = "Welcome to My Dashboard"