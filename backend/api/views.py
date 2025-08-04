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
                        "total adset" : len(summary_df),
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




# class PredictionsView(APIView):
#     def get(self, request):
#         # 1. Filter campaigns from the last 24 hours
#         now = timezone.now()
#         last_24_hours = now - timedelta(hours=24)
#         campaigns = campaigns = Campaign.objects.filter(timestamp__gte=last_24_hours).distinct()
#         serializer = CampaignSerializer(campaigns, many=True)

#         # 2. Flatten JSON: campaign + metrics
#         flat_data_list = []
#         for campaign_data in serializer.data:
#             flat_data = {
#                 **{k: v for k, v in campaign_data.items() if k != 'metrics'},
#                 **campaign_data.get('metrics', {})
#             }
#             flat_data_list.append(flat_data)
#         df = pd.DataFrame(flat_data_list)

#         if df.empty:
#             return Response({
#                 "success": False,
#                 "message": "No campaign data found in the last 24 hours."
#             })

#         # 3. Create 8 DataFrames by state and drop duplicate campaign_id in each
#         grouped_dfs = []
#         df['state'] = pd.to_numeric(df.get('state', -1), errors='coerce').fillna(-1).astype(int)
#         for i in range(8):
#             state_df = df[df['state'] == i].copy()
#             state_df = state_df.drop_duplicates(subset='campaign_id', keep='last').reset_index(drop=True)
#             grouped_dfs.append(state_df)

#         # 4. Combine all 8 DataFrames
#         combined_df = pd.concat(grouped_dfs, ignore_index=True)

#         # 5. Ensure numeric metric fields
#         metric_fields = [
#             'cost', 'revenue', 'profit', 'clicks', 'conversions',
#             'conversion_rate', 'roi', 'cpc', 'profit_margin'
#         ]
#         for field in metric_fields:
#             combined_df[field] = pd.to_numeric(combined_df.get(field, 0), errors='coerce').fillna(0)

#         # 6. Average metrics per campaign
#         avg_df = combined_df.groupby(['campaign_id', 'campaign_name'], as_index=False)[metric_fields].mean()

#         if avg_df.empty:
#             return Response({
#                 "success": False,
#                 "message": "No campaign data with valid metrics."
#             })

#         # 7. Run recommendation model
#         scaler, dbscan, features = load_model()
#         processed_df = preprocess(avg_df.copy(), features)
#         X = processed_df[features].copy()
#         X = scaler.transform(X)
#         cluster_labels = dbscan.fit_predict(X)
#         recommendations = map_clusters_to_recommendations(processed_df, cluster_labels)

#         # 8. Final response with all fields
#         output = []
#         for row, rec in zip(avg_df.to_dict(orient="records"), recommendations):
#             output.append({
#                 "campaign_id": row["campaign_id"],
#                 "campaign": row["campaign_name"],
#                 "recommendation": rec,
#                 "cost": row["cost"],
#                 "revenue": row["revenue"],
#                 "profit": row["profit"],
#                 "clicks": row["clicks"],
#                 "conversions": row["conversions"],
#                 "conversion_rate": row["conversion_rate"],
#                 "roi": row["roi"],
#                 "cpc": row["cpc"],
#                 "profit_margin": row["profit_margin"]
#             })

#         return Response({
#             "success": True,
#             "recommendations": output
#         })