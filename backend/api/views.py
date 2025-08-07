import requests
from datetime import datetime, timedelta
from rest_framework.views import APIView
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
            # df = df.dropna(subset=["sub_id_6", "sub_id_5", "sub_id_2", "sub_id_3"], how="all")
            # df.to_csv("media/row_data_time_range.csv", index=False)
            

            def is_empty_or_placeholder(val):
                if pd.isna(val):
                    return True
                if isinstance(val, str) and (val.strip() == "" or val.strip().startswith("{{")):
                    return True
                return False

            df = df.applymap(lambda x: pd.NA if is_empty_or_placeholder(x) else x)
            # df.to_csv("media/row_data_time_range.csv", index=False)

            for col in ['sub_id_2', 'sub_id_3']:
                if col in df.columns and df[col].isna().all():
                    df.drop(columns=col, inplace=True)

            cols_to_check = ['sub_id_6', 'sub_id_5', 'sub_id_3', 'sub_id_2']
            cols_existing = [col for col in cols_to_check if col in df.columns]
            df = df.dropna(subset=cols_existing, how='all')

            df["geo"] = df["sub_id_6"].apply(extract_geo)
            df["country"] = df["geo"].apply(extract_country_name)


            df.to_csv("media/row_data_time_range.csv", index=False)
            df.to_json("media/preprocess_data_time_range.json", orient='records', indent=2)

            data_path =os.path.join(settings.MEDIA_ROOT, 'preprocess_data_time_range.json')

            # Call your processing function which returns a list of dicts
            processed_data = main(data_path)

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

            # Group data for output
            grouped = defaultdict(list)
            for item in processed_data:
                key = (item.get('sub_id_6'), item.get('sub_id_3'), item.get('day'))
                grouped[key].append(item)

            output = []
            for (sub_id_6, sub_id_3, day), items in grouped.items():
                output.append({
                    "id": str(uuid.uuid4()),
                    "sub_id_6": sub_id_6,
                    "sub_id_3": sub_id_3,
                    "day": day,
                    "adset": items
                })

            # Sort output by day (latest to oldest)
            output.sort(key=lambda x: x['day'], reverse=True)

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

            return Response({'success': True, 'data': output, 'summary': summary}, status=status.HTTP_200_OK)

        except requests.RequestException as e:
            # For network-related errors
            return Response({'success': False, 'error': f'API request failed: {str(e)}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as e:
            # General catch-all for unexpected errors
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

                output.append({
                    "id": str(uuid.uuid4()),
                    "sub_id_6": sub_id_6,
                    "sub_id_3": sub_id_3,
                    "total_cost": round(df_group['cost'].sum(), 2),
                    "total_revenue": round(df_group['revenue'].sum(), 2),
                    "total_profit": round(df_group['profit'].sum(), 2),
                    "total_clicks": int(df_group['clicks'].sum()),
                    "average_cpc": round(df_group['cpc'].sum(), 4) if 'cpc' in df_group else None,
                    "average_roi": round(df_group['roi_confirmed'].sum(), 4) if 'roi_confirmed' in df_group else None,
                    "average_conversion_rate": round(df_group['conversion_rate'].sum(), 4) if 'conversion_rate' in df_group else None,
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

            return Response({'success': True, 'data': final_results, 'summary': summary}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
