import requests
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
import numpy as np
from django.utils import timezone
from scipy.stats import linregress
from api.models import  CampaignAdSet, AdSetTimeRange
from api.utills.utills import load_model, preprocess, map_clusters_to_recommendations
from django.conf import settings
from threading import Lock
from api.serializers import CampaignSerializer
from api.utills.live_inference import main
import json
from django.utils.timezone import make_aware
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
import re
from api.utills.country import extract_country_name
import uuid
from api.utills.combine_inference import enrich_campaign_data
from .models import AdsetStatus
from .serializers import AdsetStatusSerializer


# Global state tracker for cycling state 0-7
if not hasattr(settings, 'CAMPAIGN_STATE'):  # Only add if not present
    settings.CAMPAIGN_STATE = 0
    settings.CAMPAIGN_STATE_LOCK = Lock()

def extract_geo(sub_id_6):
    if not isinstance(sub_id_6, str):
        return None
    # Pattern 1: URL-style
    parts = re.split(r"\+-\+|\s-\s", sub_id_6)
    if len(parts) >= 2:
        return parts[1].strip()
    return None

class PredictCampaignsView(APIView):
    def get(self, request):
        try:
            # API config
            api_key = os.getenv("API_KEY")
            base_url = "https://tracktheweb.online/admin_api/v1"
            all_data_items = []

            # Use current Amsterdam time for both start and end date
            now_amsterdam = datetime.now(ZoneInfo("Europe/Amsterdam"))
            start_date = now_amsterdam
            end_date = now_amsterdam

            payload = {
                "range": {
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "timezone": "Europe/Amsterdam"
                },
                "columns": ["clicks", "day", "lp_clicks", "lp_ctr", "cr", "cpc"],
                "metrics": [
                    "clicks", "cost", "campaign_unique_clicks", "conversions",
                    "roi_confirmed", "revenue", "profit"
                ],
                "grouping": ["sub_id_6", "sub_id_5", "sub_id_2", "sub_id_3"],
                "filters": [],
                "summary": False,
                "limit": 100000,
                "offset": 0,
                "extended": True
            }

            headers = {
                "Api-Key": api_key,
                "Content-Type": "application/json"
            }

            response = requests.post(
                f"{base_url}/report/build",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Save raw API response
            with open('api_response.json', 'w') as f:
                json.dump(data, f, indent=4)

            rows = data.get('rows', [])
            if not rows:
                return Response({'success': True, 'data': [], 'summary': {}}, status=status.HTTP_200_OK)

            df = pd.DataFrame(rows)

            df.to_csv("media/row_data.csv", index=False)

            def is_empty_or_placeholder(val):
                if pd.isna(val):
                    return True
                if isinstance(val, str) and (val.strip() == "" or val.strip().startswith("{{")):
                    return True
                return False

            df = df.applymap(lambda x: pd.NA if is_empty_or_placeholder(x) else x)

            for col in ['sub_id_2', 'sub_id_3']:
                if col in df.columns and df[col].isna().all():
                    df.drop(columns=col, inplace=True)

            cols_to_check = ['sub_id_6', 'sub_id_5', 'sub_id_3', 'sub_id_2']
            cols_existing = [col for col in cols_to_check if col in df.columns]
            df = df.dropna(subset=cols_existing, how='all')

            if 'sub_id_2' in df.columns:
                df = df.drop_duplicates(subset='sub_id_2', keep='first')

            df["geo"] = df["sub_id_6"].apply(extract_geo)
            df["country"] = df["geo"].apply(extract_country_name)

            df.to_csv("media/row_data.csv", index=False)
            df.to_json("media/preprocess_data.json", orient='records', indent=2)

            data_path =os.path.join(settings.MEDIA_ROOT, 'preprocess_data.json')

            data = main(data_path)

            for item in data:

                try:
                    fb_adset_id = item.get('sub_id_2')
                    if fb_adset_id is None or not str(fb_adset_id).isdigit():
                        continue

                    CampaignAdSet.objects.create(
                        sub_id_6=item.get('sub_id_6', ''),
                        sub_id_5=item.get('sub_id_5', ''),
                        sub_id_2=str(item.get('sub_id_2', '')),
                        sub_id_3=str(item.get('sub_id_3', '')),
                        day=item.get('day', datetime.today().date()),

                        clicks=item.get('clicks', 0),
                        lp_clicks=item.get('lp_clicks', 0),
                        lp_ctr=item.get('lp_ctr', 0.0),
                        cr=item.get('cr', 0.0),

                        cost=item.get('cost', 0.0),
                        campaign_unique_clicks=item.get('campaign_unique_clicks', 0),
                        conversions=item.get('conversions', 0),
                        roi_confirmed=item.get('roi_confirmed', 0.0),
                        revenue=item.get('revenue', 0.0),
                        profit=item.get('profit', 0.0),
                        revenue_to_cost_ratio=item.get('revenue_to_cost_ratio', 0.0),
                        conversion_rate=item.get('conversion_rate', 0.0),
                        profit_margin=item.get('profit_margin', 0.0),
                        cluster=item.get('cluster', -1),

                        recommendation=item.get('recommendation', ''),
                        reason=item.get('reason', ''),
                        suggestion=item.get('suggestion', ''),
                        priority=item.get('priority', 0),
                        urgent=item.get('urgent', False),
                        action_needed=item.get('action_needed', False),
                        potential_impact=item.get('potential_impact', 0.0)
                    )

                except Exception as e:
                    print(f"[ERROR] Creating campaign performance entry failed: {e}")

            all_data_items.extend(data)
            grouped = defaultdict(list)

            for item in data:
                key = (item['sub_id_6'], item['sub_id_3'])
                grouped[key].append(item)

            output = []
            for (sub_id_6, sub_id_3), items in grouped.items():
                output.append({
                    "id": str(uuid.uuid4()),
                    "sub_id_6": sub_id_6,
                    "sub_id_3": sub_id_3,
                    "adset": items
                })

            summary = {}
            if all_data_items:
                summary_df = pd.DataFrame(all_data_items)
                if not summary_df.empty:
                    summary = {
                        "total_adset" : len(summary_df),
                        "total_cost": round(summary_df['cost'].sum(), 2),
                        "total_revenue": round(summary_df['revenue'].sum(), 2),
                        "total_profit": round(summary_df['profit'].sum(), 2),
                        "total_clicks": int(summary_df['clicks'].sum()),
                        "total_conversions": int(summary_df['conversions'].sum()),
                        "average_roi": round(summary_df['roi_confirmed'].mean(), 4),
                        "average_conversion_rate": round(summary_df['conversion_rate'].mean(), 4),
                        "priority_distribution": summary_df['priority'].astype(str).value_counts().to_dict()
                    }
            else:
                summary = {}

            return Response({'success': True, 'data': output, 'summary': summary}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class PredictTimeRangeView(APIView):
    """
    API endpoint to get ad set campaign data within a date range,
    process, save in DB and return grouped result and summary.
    """

    def get(self, request):
        try:
            api_key = os.getenv("API_KEY") or getattr(settings, "API_KEY", None)
            if not api_key:
                return Response({"success": False, "error": "API_KEY not set."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            base_url = "https://tracktheweb.online/admin_api/v1"

            # Get date range params
            start_str = request.query_params.get('start_date')
            end_str = request.query_params.get('end_date')

            amsterdam_tz = ZoneInfo("Europe/Amsterdam")

            try:
                # Parse dates or fallback to now
                if start_str:
                    start_date = datetime.strptime(start_str, "%Y-%m-%d")
                    start_date = make_aware(start_date, amsterdam_tz)
                else:
                    start_date = datetime.now(amsterdam_tz)

                if end_str:
                    end_date = datetime.strptime(end_str, "%Y-%m-%d")
                    end_date = make_aware(end_date, amsterdam_tz)
                else:
                    end_date = datetime.now(amsterdam_tz)
            except ValueError:
                return Response({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

            payload = {
                "range": {
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "timezone": "Europe/Amsterdam"
                },
                "columns": ["clicks", "day", "lp_clicks", "lp_ctr", "cr", "cpc"],
                "metrics": [
                    "clicks", "cost", "campaign_unique_clicks", "conversions",
                    "roi_confirmed", "revenue", "profit"
                ],
                "grouping": ["sub_id_6", "sub_id_5", "sub_id_2", "sub_id_3"],
                "filters": [],
                "summary": False,
                "limit": 100000,
                "offset": 0,
                "extended": True
            }

            headers = {
                "Api-Key": api_key,
                "Content-Type": "application/json"
            }

            response = requests.post(f"{base_url}/report/build", headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Save raw API response for debugging
            with open('api_response.json', 'w') as f:
                json.dump(data, f, indent=4)

            rows = data.get('rows', [])
            if not rows:
                return Response({'success': True, 'data': [], 'summary': {}}, status=status.HTTP_200_OK)

            df = pd.DataFrame(rows)

            def is_empty_or_placeholder(val):
                if pd.isna(val):
                    return True
                if isinstance(val, str) and (val.strip() == "" or val.strip().startswith("{{")):
                    return True
                return False

            df = df.applymap(lambda x: pd.NA if is_empty_or_placeholder(x) else x)

            for col in ['sub_id_2', 'sub_id_3']:
                if col in df.columns and df[col].isna().all():
                    df.drop(columns=col, inplace=True)

            cols_to_check = ['sub_id_6', 'sub_id_5', 'sub_id_3', 'sub_id_2']
            cols_existing = [col for col in cols_to_check if col in df.columns]
            df = df.dropna(subset=cols_existing, how='all')

            # You must implement these extraction functions based on your data
            def extract_geo(sub_id_6):
                # Example extraction (customize as needed)
                return sub_id_6.split(" - ")[1] if " - " in sub_id_6 else None

            def extract_country_name(geo):
                # Example mapping (customize as needed)
                if geo == "US":
                    return "United States"
                return geo

            df["geo"] = df["sub_id_6"].apply(extract_geo)
            df["country"] = df["geo"].apply(extract_country_name)

            # Save preprocessed data to file (optional)
            df.to_csv("media/row_data_time_range.csv", index=False)
            df.to_json("media/preprocess_data_time_range.json", orient='records', indent=2)

            data_path = os.path.join(settings.MEDIA_ROOT, 'preprocess_data_time_range.json')

            # Your processing function (you must define it)
            processed_data = main(data_path)

            # Save all processed items
            all_data_items = []
            for item in processed_data:
                try:
                    fb_adset_id = item.get('sub_id_2')
                    if fb_adset_id is None or not str(fb_adset_id).isdigit():
                        continue

                    AdSetTimeRange.objects.create(
                        sub_id_6=item.get('sub_id_6', ''),
                        sub_id_5=item.get('sub_id_5', ''),
                        sub_id_2=str(item.get('sub_id_2', '')),
                        sub_id_3=str(item.get('sub_id_3', '')),
                        day=item.get('day', datetime.today().date()),

                        clicks=item.get('clicks', 0),
                        lp_clicks=item.get('lp_clicks', 0),
                        lp_ctr=item.get('lp_ctr', 0.0),
                        cr=item.get('cr', 0.0),

                        cost=item.get('cost', 0.0),
                        campaign_unique_clicks=item.get('campaign_unique_clicks', 0),
                        conversions=item.get('conversions', 0),
                        roi_confirmed=item.get('roi_confirmed', 0.0),
                        revenue=item.get('revenue', 0.0),
                        profit=item.get('profit', 0.0),
                        revenue_to_cost_ratio=item.get('revenue_to_cost_ratio', 0.0),
                        conversion_rate=item.get('conversion_rate', 0.0),
                        profit_margin=item.get('profit_margin', 0.0),
                        cluster=item.get('cluster', -1),

                        recommendation=item.get('recommendation', ''),
                        reason=item.get('reason', ''),
                        suggestion=item.get('suggestion', ''),
                        priority=item.get('priority', 0),
                        urgent=item.get('urgent', False),
                        action_needed=item.get('action_needed', False),
                        potential_impact=item.get('potential_impact', 0.0)
                    )

                except Exception as e:
                    print(f"[ERROR] Creating campaign performance entry failed: {e}")

            all_data_items.extend(processed_data)

            # --- NEW GROUPING LOGIC ---

            # Group by (sub_id_6, sub_id_3)
            grouped = defaultdict(list)
            for item in processed_data:
                key = (item.get('sub_id_6'), item.get('sub_id_3'))
                grouped[key].append(item)

            output = []
            for (sub_id_6, sub_id_3), items in grouped.items():
                # Group inside by day
                day_grouped = defaultdict(list)
                for adset_item in items:
                    day_key = adset_item.get('day')
                    day_grouped[day_key].append(adset_item)

                # Campaign level aggregations using pandas DataFrame
                df_campaign = pd.DataFrame(items)

                total_cost = round(df_campaign['cost'].sum(), 2)
                total_revenue = round(df_campaign['revenue'].sum(), 2)
                total_profit = round(total_revenue - total_cost, 2)
                total_clicks = int(round(df_campaign['clicks'].sum()))
                total_conversions = int(round(df_campaign['conversions'].sum()))

                total_roi = round(((total_revenue - total_cost) / total_cost) * 100, 2) if total_cost > 0 else 0
                total_conversion_rate = round((total_conversions / total_clicks) * 100, 2) if total_clicks > 0 else 0
                total_cpc = round((total_cost / total_clicks), 2) if total_clicks > 0 else 0

                # # Placeholder recommendation values - replace with your logic if needed
                # recommendation = "PAUSE"
                # recommendation_percentage = None
                # total_budget_change_pct_sum = None

                output.append({
                    "id": str(uuid.uuid4()),
                    "sub_id_6": sub_id_6,
                    "sub_id_3": sub_id_3,
                    "total_cost": total_cost,
                    "total_revenue": total_revenue,
                    "total_profit": total_profit,
                    "total_clicks": total_clicks,
                    "total_cpc": total_cpc,
                    "total_roi": total_roi,
                    "total_conversion_rate": total_conversion_rate,
                    "day": {
                        day: {"adset": adsets} for day, adsets in day_grouped.items()
                    }
                })

            # Sort output by day descending (based on the most recent day in each campaign group)
            def most_recent_day(campaign):
                # convert string date keys to datetime, get max
                try:
                    return max(datetime.strptime(d, "%Y-%m-%d") for d in campaign["day"].keys())
                except Exception:
                    return datetime.min

            output.sort(key=most_recent_day, reverse=True)

            model_path = os.path.join(settings.MEDIA_ROOT, 'dbscan_model_bundle_latest.pkl')

            final_results = []
            for group in output:  # Your grouped campaign list
                enriched = enrich_campaign_data(group, model_path=model_path)
                final_results.append(enriched)


            # Generate overall summary (optional)
            summary = {}
            if all_data_items:
                summary_df = pd.DataFrame(all_data_items)
                if not summary_df.empty:
                    summary = {
                        "total_adset": len(summary_df),
                        "total_cost": round(summary_df['cost'].sum(), 2),
                        "total_revenue": round(summary_df['revenue'].sum(), 2),
                        "total_profit": round(summary_df['profit'].sum(), 2),
                        "total_clicks": int(summary_df['clicks'].sum()),
                        "total_conversions": int(summary_df['conversions'].sum()),
                        "total_roi": round(summary_df['roi_confirmed'].mean(), 4),
                        "average_conversion_rate": round(summary_df['conversion_rate'].mean(), 4),
                        "priority_distribution": summary_df['priority'].astype(str).value_counts().to_dict()
                    }

            return Response({'success': True, 'data': final_results, 'summary': summary}, status=status.HTTP_200_OK)

        except requests.RequestException as e:
            return Response({'success': False, 'error': f'API request failed: {str(e)}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictCampaignsUpdateView(APIView):
   def get(self, request):
        try:
            # API config
            api_key = os.getenv("API_KEY")
            base_url = "https://tracktheweb.online/admin_api/v1"
            all_data_items = []

            # Use current Amsterdam time for both start and end date
            now_amsterdam = datetime.now(ZoneInfo("Europe/Amsterdam"))
            start_date = now_amsterdam
            end_date = now_amsterdam

            payload = {
                "range": {
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "timezone": "Europe/Amsterdam"
                },
                "columns": ["clicks", "day", "lp_clicks", "lp_ctr", "cr", "cpc"],
                "metrics": [
                    "clicks", "cost", "campaign_unique_clicks", "conversions",
                    "roi_confirmed", "revenue", "profit"
                ],
                "grouping": ["sub_id_6", "sub_id_5", "sub_id_2", "sub_id_3"],
                "filters": [],
                "summary": False,
                "limit": 100000,
                "offset": 0,
                "extended": True
            }

            headers = {
                "Api-Key": api_key,
                "Content-Type": "application/json"
            }

            response = requests.post(
                f"{base_url}/report/build",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Save raw API response
            with open('api_response.json', 'w') as f:
                json.dump(data, f, indent=4)

            rows = data.get('rows', [])
            if not rows:
                return Response({'success': True, 'data': [], 'summary': {}}, status=status.HTTP_200_OK)

            df = pd.DataFrame(rows)

            df.to_csv("media/row_data.csv", index=False)

            def is_empty_or_placeholder(val):
                if pd.isna(val):
                    return True
                if isinstance(val, str) and (val.strip() == "" or val.strip().startswith("{{")):
                    return True
                return False

            df = df.applymap(lambda x: pd.NA if is_empty_or_placeholder(x) else x)

            for col in ['sub_id_2', 'sub_id_3']:
                if col in df.columns and df[col].isna().all():
                    df.drop(columns=col, inplace=True)

            cols_to_check = ['sub_id_6', 'sub_id_5', 'sub_id_3', 'sub_id_2']
            cols_existing = [col for col in cols_to_check if col in df.columns]
            df = df.dropna(subset=cols_existing, how='all')

            if 'sub_id_2' in df.columns:
                df = df.drop_duplicates(subset='sub_id_2', keep='first')

            df["geo"] = df["sub_id_6"].apply(extract_geo)
            df["country"] = df["geo"].apply(extract_country_name)

            df.to_csv("media/row_data.csv", index=False)
            df.to_json("media/preprocess_data.json", orient='records', indent=2)

            data_path =os.path.join(settings.MEDIA_ROOT, 'preprocess_data.json')

            data = main(data_path)

            
            all_data_items.extend(data)
            grouped = defaultdict(list)

            for item in data:
                key = (item['sub_id_6'], item['sub_id_3'])
                grouped[key].append(item)

            output = []
            for (sub_id_6, sub_id_3), items in grouped.items():
                df_group = pd.DataFrame(items)

                total_cost = round(df_group['cost'].sum(), 2)
                total_revenue = round(df_group['revenue'].sum(), 2)
                total_profit = round(total_revenue - total_cost, 2)
                total_clicks = int(round(df_group['clicks'].sum()))
                total_conversions = int(round(df_group['conversions'].sum()))

                total_roi = round(((total_revenue - total_cost) / total_cost) * 100, 2) if total_cost > 0 else 0
                total_conversion_rate = round((total_conversions / total_clicks) * 100, 2) if total_clicks > 0 else 0
                total_cpc = round((total_cost / total_clicks), 2) if total_clicks > 0 else 0

                # Group items by 'day'
                day_dict = defaultdict(lambda: {"adset": []})
                for adset in items:
                    day_dict[adset["day"]]["adset"].append(adset)

                output.append({
                    "id": str(uuid.uuid4()),
                    "sub_id_6": sub_id_6,
                    "sub_id_3": sub_id_3,
                    "total_cost": total_cost,
                    "total_revenue": total_revenue,
                    "total_profit": total_profit,
                    "total_clicks": total_clicks,
                    "total_cpc": total_cpc,
                    "total_roi": total_roi,
                    "total_conversion_rate": total_conversion_rate,
                    "day": dict(day_dict)  # note key changed from 'adset' list to grouped by day
                })

            model_path = os.path.join(settings.MEDIA_ROOT, 'dbscan_model_bundle_latest.pkl')

            final_results = []
            for group in output:  # Your grouped campaign list
                enriched = enrich_campaign_data(group, model_path=model_path)
                final_results.append(enriched)

            summary = {}
            if all_data_items:
                summary_df = pd.DataFrame(all_data_items)
                if not summary_df.empty:
                    total_cost = round(summary_df['cost'].sum(), 2)
                    total_revenue = round(summary_df['revenue'].sum(), 2)
                    total_roi = round(((total_revenue - total_cost) / total_cost) * 100, 2) if total_cost > 0 else 0
                    summary = {
                        "total_adset" : len(summary_df),
                        "total_cost": round(summary_df['cost'].sum(), 2),
                        "total_revenue": round(summary_df['revenue'].sum(), 2),
                        "total_profit": round(summary_df['profit'].sum(), 2),
                        "total_clicks": int(summary_df['clicks'].sum()),
                        "total_conversions": int(summary_df['conversions'].sum()),
                        "total_roi": total_roi,
                        "average_conversion_rate": round(summary_df['conversion_rate'].mean(), 4),
                        "priority_distribution": summary_df['priority'].astype(str).value_counts().to_dict()
                    }
            else:
                summary = {}

            return Response({'success': True, 'data': final_results, 'summary': summary}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PredictCampaignsDailyView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            # API config
            api_key = os.getenv("API_KEY")
            base_url = "https://tracktheweb.online/admin_api/v1"
            all_data_items = []

            # Use current Amsterdam time for both start and end date
            now_amsterdam = datetime.now(ZoneInfo("Europe/Amsterdam"))
            start_date = now_amsterdam
            end_date = now_amsterdam

            payload = {
                "range": {
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "timezone": "Europe/Amsterdam"
                },
                "columns": ["clicks", "day", "lp_clicks", "lp_ctr", "cr", "cpc"],
                "metrics": [
                    "clicks", "cost", "campaign_unique_clicks", "conversions",
                    "roi_confirmed", "revenue", "profit"
                ],
                "grouping": ["sub_id_6", "sub_id_5", "sub_id_2", "sub_id_3"],
                "filters": [],
                "summary": False,
                "limit": 100000,
                "offset": 0,
                "extended": True
            }

            headers = {
                "Api-Key": api_key,
                "Content-Type": "application/json"
            }

            response = requests.post(
                f"{base_url}/report/build",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Save raw API response
            with open('api_response.json', 'w') as f:
                json.dump(data, f, indent=4)

            rows = data.get('rows', [])
            if not rows:
                return Response({'success': True, 'data': [], 'summary': {}}, status=status.HTTP_200_OK)

            # ✅ Optimized insert
            adset_ids = {row.get("sub_id_2") for row in rows if row.get("sub_id_2")}
            if adset_ids:
                existing_ids = set(
                    AdsetStatus.objects.filter(adset_id__in=adset_ids).values_list("adset_id", flat=True)
                )
                new_ids = adset_ids - existing_ids
                new_records = [AdsetStatus(adset_id=adset_id, is_active=True) for adset_id in new_ids]
                AdsetStatus.objects.bulk_create(new_records, ignore_conflicts=True)

            df = pd.DataFrame(rows)

            df.to_csv("media/row_data.csv", index=False)

            def is_empty_or_placeholder(val):
                if pd.isna(val):
                    return True
                if isinstance(val, str) and (val.strip() == "" or val.strip().startswith("{{")):
                    return True
                return False

            df = df.applymap(lambda x: pd.NA if is_empty_or_placeholder(x) else x)

            for col in ['sub_id_2', 'sub_id_3']:
                if col in df.columns and df[col].isna().all():
                    df.drop(columns=col, inplace=True)

            cols_to_check = ['sub_id_6', 'sub_id_5', 'sub_id_3', 'sub_id_2']
            cols_existing = [col for col in cols_to_check if col in df.columns]
            df = df.dropna(subset=cols_existing, how='all')

            if 'sub_id_2' in df.columns:
                df = df.drop_duplicates(subset='sub_id_2', keep='first')

            df["geo"] = df["sub_id_6"].apply(extract_geo)
            df["country"] = df["geo"].apply(extract_country_name)

            df.to_csv("media/row_data.csv", index=False)
            df.to_json("media/preprocess_data.json", orient='records', indent=2)

            data_path =os.path.join(settings.MEDIA_ROOT, 'preprocess_data.json')

            data = main(data_path)
            # print("data:", data)

            # 1. Extract all adset_ids from your data
            adset_ids = {row['sub_id_2'] for row in data if row.get('sub_id_2')}

            # 2. Query DB once and create a map
            status_map = {
                obj.adset_id: 'active' if obj.is_active else 'paused'
                for obj in AdsetStatus.objects.filter(adset_id__in=adset_ids)
            }

            # 3. Enrich each row
            for row in data:
                adset_id = row.get('sub_id_2')
                row['status'] = status_map.get(adset_id, 'unknown')  # 'unknown' if not in DB

            all_data_items.extend(data)
            grouped = defaultdict(list)

            for item in data:
                key = (item['sub_id_6'], item['sub_id_3'])
                grouped[key].append(item)

            output = []
            for (sub_id_6, sub_id_3), items in grouped.items():
                df_group = pd.DataFrame(items)

                total_cost = round(df_group['cost'].sum(), 2)
                total_revenue = round(df_group['revenue'].sum(), 2)
                total_profit = round(total_revenue - total_cost, 2)
                total_clicks = int(round(df_group['clicks'].sum()))
                total_conversions = int(round(df_group['conversions'].sum()))

                total_roi = round(((total_revenue - total_cost) / total_cost) * 100, 2) if total_cost > 0 else 0
                total_conversion_rate = round((total_conversions / total_clicks) * 100, 2) if total_clicks > 0 else 0
                total_cpc = round((total_cost / total_clicks), 2) if total_clicks > 0 else 0

                # ✅ Pick geo and country from first item in the group
                geo = items[0].get("geo")
                country = items[0].get("country")

                output.append({
                    "id": str(uuid.uuid4()),
                    "sub_id_6": sub_id_6,
                    "sub_id_3": sub_id_3,
                    "total_cost": total_cost,
                    "total_revenue": total_revenue,
                    "total_profit": total_profit,
                    "total_clicks": total_clicks,
                    "total_cpc": total_cpc,
                    "total_roi": total_roi,
                    "geo": geo,
                    "country": country,
                    "total_conversion_rate": total_conversion_rate,
                    "adset": items
                })

            model_path = os.path.join(settings.MEDIA_ROOT, 'dbscan_model_bundle_latest.pkl')

            final_results = []
            for group in output:  # Your grouped campaign list
                enriched = enrich_campaign_data(group, model_path=model_path)
                final_results.append(enriched)

            summary = {}
            if all_data_items:
                summary_df = pd.DataFrame(all_data_items)
                if not summary_df.empty:
                    total_cost = round(summary_df['cost'].sum(), 2)
                    total_revenue = round(summary_df['revenue'].sum(), 2)
                    total_roi = round(((total_revenue - total_cost) / total_cost) * 100, 2) if total_cost > 0 else 0

                    summary = {
                        "total_adset" : len(summary_df),
                        "total_cost": round(summary_df['cost'].sum(), 2),
                        "total_revenue": round(summary_df['revenue'].sum(), 2),
                        "total_profit": round(summary_df['profit'].sum(), 2),
                        "total_clicks": int(summary_df['clicks'].sum()),
                        "total_conversions": int(summary_df['conversions'].sum()),
                        "total_roi": total_roi,
                        "average_conversion_rate": round(summary_df['conversion_rate'].mean(), 4),
                        "priority_distribution": summary_df['priority'].astype(str).value_counts().to_dict()
                    }
            else:
                summary = {}

            return Response({'success': True, 'data': final_results, 'summary': summary}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class PredictDateRangeView(APIView):
    permission_classes = [IsAuthenticated]
    """
    API endpoint to get ad set campaign data within a date range,
    process, save in DB and return grouped result and summary.
    """

    def get(self, request):
        try:
            api_key = os.getenv("API_KEY") or getattr(settings, "API_KEY", None)
            if not api_key:
                return Response({"success": False, "error": "API_KEY not set."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            base_url = "https://tracktheweb.online/admin_api/v1"

            # Get date range params
            start_str = request.query_params.get('start_date')
            end_str = request.query_params.get('end_date')

            amsterdam_tz = ZoneInfo("Europe/Amsterdam")

            try:
                # Parse dates or fallback to now
                if start_str:
                    start_date = datetime.strptime(start_str, "%Y-%m-%d")
                    start_date = make_aware(start_date, amsterdam_tz)
                else:
                    start_date = datetime.now(amsterdam_tz)

                if end_str:
                    end_date = datetime.strptime(end_str, "%Y-%m-%d")
                    end_date = make_aware(end_date, amsterdam_tz)
                else:
                    end_date = datetime.now(amsterdam_tz)
            except ValueError:
                return Response({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

            payload = {
                "range": {
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "timezone": "Europe/Amsterdam"
                },
                "columns": ["clicks", "day", "lp_clicks", "lp_ctr", "cr", "cpc"],
                "metrics": [
                    "clicks", "cost", "campaign_unique_clicks", "conversions",
                    "roi_confirmed", "revenue", "profit"
                ],
                "grouping": ["sub_id_6", "sub_id_5", "sub_id_2", "sub_id_3"],
                "filters": [],
                "summary": False,
                "limit": 100000,
                "offset": 0,
                "extended": True
            }

            headers = {
                "Api-Key": api_key,
                "Content-Type": "application/json"
            }

            response = requests.post(f"{base_url}/report/build", headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Save raw API response for debugging
            with open('api_response.json', 'w') as f:
                json.dump(data, f, indent=4)

            rows = data.get('rows', [])
            if not rows:
                return Response({'success': True, 'data': [], 'summary': {}}, status=status.HTTP_200_OK)

            df = pd.DataFrame(rows)

            def is_empty_or_placeholder(val):
                if pd.isna(val):
                    return True
                if isinstance(val, str) and (val.strip() == "" or val.strip().startswith("{{")):
                    return True
                return False

            df = df.applymap(lambda x: pd.NA if is_empty_or_placeholder(x) else x)

            for col in ['sub_id_2', 'sub_id_3']:
                if col in df.columns and df[col].isna().all():
                    df.drop(columns=col, inplace=True)

            cols_to_check = ['sub_id_6', 'sub_id_5', 'sub_id_3', 'sub_id_2']
            cols_existing = [col for col in cols_to_check if col in df.columns]
            df = df.dropna(subset=cols_existing, how='all')

            def extract_geo(sub_id_6):
                return sub_id_6.split(" - ")[1] if " - " in sub_id_6 else None

            df["geo"] = df["sub_id_6"].apply(extract_geo)
            df["country"] = df["geo"].apply(extract_country_name)

            df = df.groupby('sub_id_2').agg({
                'cost': 'sum',
                'revenue': 'sum',
                'clicks': 'sum',
                'lp_clicks': 'sum',
                'conversions': 'sum',
                'campaign_unique_clicks': 'sum',
                'sub_id_6': 'first',
                'sub_id_5': 'first',
                'sub_id_3': 'first',
                'day': 'first',
                'geo': 'first',
                'country': 'first'
            }).reset_index()

            df['profit'] = df['revenue'] - df['cost']
            df['cpc'] = df.apply(lambda x: x['cost'] / x['clicks'] if x['clicks'] > 0 else 0, axis=1)
            df['roi_confirmed'] = df.apply(lambda x: (x['profit'] / x['cost']) * 100 if x['cost'] > 0 else 0, axis=1)

            df['lp_ctr'] = df.apply(lambda x: (x['lp_clicks'] / x['clicks']) * 100 if x['clicks'] > 0 else 0, axis=1)
            df['cr'] = df.apply(lambda x: (x['conversions'] / x['clicks']) * 100 if x['clicks'] > 0 else 0, axis=1)

            df.to_csv("media/row_data_time_range.csv", index=False)
            df.to_json("media/preprocess_data_time_range.json", orient='records', indent=2)

            data_path = os.path.join(settings.MEDIA_ROOT, 'preprocess_data_time_range.json')

            processed_data = main(data_path)

            all_data_items = []
            all_data_items.extend(processed_data)

            # ----------- New grouping function -----------
            def group_processed_data(data):
                grouped = defaultdict(list)
                for item in data:
                    key = (item['sub_id_6'], item['sub_id_3'])
                    grouped[key].append(item)

                output = []
                for (sub_id_6, sub_id_3), items in grouped.items():
                    df_group = pd.DataFrame(items)

                    total_cost = round(df_group['cost'].sum(), 2)
                    total_revenue = round(df_group['revenue'].sum(), 2)
                    total_profit = round(total_revenue - total_cost, 2)
                    total_clicks = int(round(df_group['clicks'].sum()))
                    total_conversions = int(round(df_group['conversions'].sum()))

                    total_roi = round(((total_revenue - total_cost) / total_cost) * 100, 2) if total_cost > 0 else 0
                    total_conversion_rate = round((total_conversions / total_clicks) * 100, 2) if total_clicks > 0 else 0
                    total_cpc = round((total_cost / total_clicks), 2) if total_clicks > 0 else 0

                    # ✅ Pick geo and country from first item in the group
                    geo = items[0].get("geo")
                    country = items[0].get("country")

                    output.append({
                        "id": str(uuid.uuid4()),
                        "sub_id_6": sub_id_6,
                        "sub_id_3": sub_id_3,
                        "total_cost": total_cost,
                        "total_revenue": total_revenue,
                        "total_profit": total_profit,
                        "total_clicks": total_clicks,
                        "total_cpc": total_cpc,
                        "geo": geo,
                        "country": country,
                        "total_roi": total_roi,
                        "total_conversion_rate": total_conversion_rate,
                        "adset": items
                    })
                return output

            output = group_processed_data(processed_data)

            model_path = os.path.join(settings.MEDIA_ROOT, 'dbscan_model_bundle_latest.pkl')

            final_results = []
            for group in output:  # Your grouped campaign list
                enriched = enrich_campaign_data(group, model_path=model_path)
                final_results.append(enriched)

            summary = {}
            if all_data_items:
                summary_df = pd.DataFrame(all_data_items)
                if not summary_df.empty:
                    total_cost = round(summary_df['cost'].sum(), 2)
                    total_revenue = round(summary_df['revenue'].sum(), 2)
                    total_roi = round(((total_revenue - total_cost) / total_cost) * 100, 2) if total_cost > 0 else 0

                    summary = {
                        "total_adset" : len(summary_df),
                        "total_cost": round(summary_df['cost'].sum(), 2),
                        "total_revenue": round(summary_df['revenue'].sum(), 2),
                        "total_profit": round(summary_df['profit'].sum(), 2),
                        "total_clicks": int(summary_df['clicks'].sum()),
                        "total_conversions": int(summary_df['conversions'].sum()),
                        "total_roi": total_roi,
                        "average_conversion_rate": round(summary_df['conversion_rate'].mean(), 4),
                        "priority_distribution": summary_df['priority'].astype(str).value_counts().to_dict()
                    }
            else:
                summary = {}

            return Response({'success': True, 'data': final_results, 'summary': summary}, status=status.HTTP_200_OK)

        except requests.RequestException as e:
            return Response({'success': False, 'error': f'API request failed: {str(e)}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdateAdsetStatusAPIView(APIView):

    permission_classes = [IsAuthenticated]
    """
    Update the is_active status of an AdsetStatus by adset_id.
    """

    def post(self, request, *args, **kwargs):
        adset_id = request.data.get('adset_id')
        is_active = request.data.get('is_active')

        if adset_id is None or is_active is None:
            return Response(
                {"error": "adset_id and is_active are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            adset = AdsetStatus.objects.get(adset_id=adset_id)
        except AdsetStatus.DoesNotExist:
            return Response(
                {"error": "Adset not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Update the value
        adset.is_active = is_active
        adset.save()

        serializer = AdsetStatusSerializer(adset)
        return Response(serializer.data, status=status.HTTP_200_OK)