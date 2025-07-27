import requests
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
import numpy as np
from django.utils import timezone
from scipy.stats import linregress
from api.models import Campaign, CampaignAd
from api.utills.utills import load_model, preprocess, map_clusters_to_recommendations
from django.conf import settings
from threading import Lock
from api.serializers import CampaignSerializer
from api.utills.live_inference import main
import json
from collections import defaultdict
from datetime import datetime

# Global state tracker for cycling state 0-7
if not hasattr(settings, 'CAMPAIGN_STATE'):  # Only add if not present
    settings.CAMPAIGN_STATE = 0
    settings.CAMPAIGN_STATE_LOCK = Lock()

class PredictCampaignsView(APIView):
    def get(self, request):
        try:
            # Load model
            scaler, dbscan, features = load_model()

            # Extract parameters
            api_key = 'c1da605a864e6c74beb71d3a713e019c'
            base_url = "https://tracktheweb.online/admin_api/v1"
            hours_back = int(request.GET.get('hours_back', 24))

            time_ranges = [hours_back]
            # final_output = []
            all_data_items = []

            for time_range in time_ranges:
                end_date = datetime.now()
                start_date = end_date - timedelta(hours=time_range)

                payload = {
                    "range": {
                        "from": start_date.strftime("%Y-%m-%d"),
                        "to": end_date.strftime("%Y-%m-%d"),
                        "timezone": "Europe/Amsterdam"
                    },
                    "columns":  [
                        "campaign", "campaign_id", "cost", "revenue", "profit",
                        "clicks", "campaign_unique_clicks", "conversions", "roi_confirmed",
                        "datetime", "lp_clicks", "cr", "lp_ctr"
                    ],
                    "metrics": [
                        "clicks",
                        "cost",
                        "campaign_unique_clicks",
                        "conversions",
                        "roi_confirmed"
                    ],
                    "grouping": [
                        "sub_id_6",
                        "sub_id_5",
                        "sub_id_3",
                        "sub_id_2"
                    ],
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
                # print(data)

                with open('api_response.json', 'w') as f:
                    json.dump(data, f, indent=4)  

                rows = data.get('rows', [])
                # print("rows:", rows)
                

                if not rows:
                    continue

                # # Print unique campaign_id values and their count
                # unique_campaign_ids = set(row.get('campaign_id') for row in rows if 'campaign_id' in row)
                # print(f"Number of unique campaign_id: {len(unique_campaign_ids)}")
                # print(f"Unique campaign_id values: {unique_campaign_ids}")

                df = pd.DataFrame(rows)

                # Function to detect empty strings or placeholders like {{campaign.name}}
                def is_empty_or_placeholder(val):
                    if pd.isna(val):
                        return True
                    if isinstance(val, str) and (val.strip() == "" or val.strip().startswith("{{")):
                        return True
                    return False

                # Replace those with pd.NA
                df = df.applymap(lambda x: pd.NA if is_empty_or_placeholder(x) else x)

                # Drop sub_id_2 and sub_id_3 if all values are NA
                for col in ['sub_id_2', 'sub_id_3']:
                    if col in df.columns and df[col].isna().all():
                        df.drop(columns=col, inplace=True)

                # Drop rows where all of sub_id_6, sub_id_5, sub_id_3, sub_id_2 are empty
                cols_to_check = ['sub_id_6', 'sub_id_5', 'sub_id_3', 'sub_id_2']
                cols_existing = [col for col in cols_to_check if col in df.columns]
                df = df.dropna(subset=cols_existing, how='all')

                # Convert the 'datetime' column to datetime
                df['datetime'] = pd.to_datetime(df['datetime'])

                # Sort the DataFrame
                df = df.sort_values(by=['sub_id_2' if 'sub_id_2' in df.columns else 'campaign_id', 'datetime'])

                if 'sub_id_2' in df.columns:
                    df = df.sort_values(by='datetime', ascending=False)  # latest datetime first
                    df = df.drop_duplicates(subset='sub_id_2', keep='first')

                # Save to CSV
                df.to_csv("media/row_data.csv", index=False)
                df.to_json("media/preprocess_data.json", orient='records', indent=2)

                data = main()

                for item in data:
                    try:
                        fb_adset_id = item.get('sub_id_2')
                        if fb_adset_id is None or not str(fb_adset_id).isdigit():
                            continue  # skip invalid adsets

                        fb_adset_id = int(fb_adset_id)
                        timestamp_ms = item.get('datetime')
                        timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)

                        CampaignAd.objects.create(
                            fb_campaign_id=item.get('campaign_id', 0),
                            fb_adset_id=fb_adset_id,
                            fb_campaign_name=item.get('campaign', ''),
                            cost=item.get('cost', 0.0),
                            revenue=item.get('revenue', 0.0),
                            profit=item.get('profit', 0.0),
                            clicks=item.get('clicks', 0),
                            campaign_unique_clicks=item.get('campaign_unique_clicks', 0),
                            conversions=item.get('conversions', 0),
                            roi_confirmed=item.get('roi_confirmed', 0.0),
                            timestamp=timestamp,
                            lp_clicks=item.get('lp_clicks', 0),
                            cr=item.get('cr', 0.0),
                            lp_ctr=item.get('lp_ctr', 0.0),
                            sub_id_2=str(item.get('sub_id_2', '')),
                            sub_id_3=str(item.get('sub_id_3', '')),
                            sub_id_5=str(item.get('sub_id_5', '')),
                            sub_id_6=str(item.get('sub_id_6', '')),
                            log_revenue=item.get('revenue_to_cost_ratio', 0.0),  # remapped
                            log_cr=item.get('conversion_rate', 0.0),              # remapped
                            cluster=item.get('cluster', -1),
                            recommendation=item.get('recommendation', ''),
                            reason=item.get('reason', ''),
                            urgency=item.get('urgency', ''),
                            priority=str(item.get('priority', ''))
                        )

                    except Exception as e:
                        print(f"[ERROR] Creating campaign ad failed: {e}")

                all_data_items.extend(data)
                grouped = defaultdict(list)

                for item in data:
                    key = (item['sub_id_6'], item['sub_id_3'])
                    grouped[key].append(item)

                # Convert to desired output format
                output = []
                for (sub_id_6, sub_id_3), items in grouped.items():
                    output.append({
                        "sub_id_6": sub_id_6,
                        "sub_id_3": sub_id_3,
                        "adset": items
                    })

                # Calculate summary
                summary_data = pd.DataFrame(all_data_items)
                if not summary_data.empty:
                    total_cost = summary_data['cost'].sum()
                    total_revenue = summary_data['revenue'].sum()
                    total_profit = summary_data['profit'].sum()
                    total_clicks = summary_data['clicks'].sum()
                    total_conversions = summary_data['conversions'].sum()
                    avg_roi = summary_data['roi_confirmed'].mean()
                    avg_cr = summary_data['conversion_rate'].mean()
                    priority_dist = summary_data['priority'].astype(str).value_counts().to_dict()

                    summary = {
                        "total_cost": round(total_cost, 2),
                        "total_revenue": round(total_revenue, 2),
                        "total_profit": round(total_profit, 2),
                        "total_clicks": int(total_clicks),
                        "total_conversions": int(total_conversions),
                        "average_roi": round(avg_roi, 4),
                        "average_conversion_rate": round(avg_cr, 4),
                        "priority_distribution": priority_dist
                    }
                else:
                    summary = {}

            return Response({'success': True, 'data': output, 'summary': summary}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class PredictionsView(APIView):
    def get(self, request):
        # 1. Filter campaigns from the last 24 hours
        now = timezone.now()
        last_24_hours = now - timedelta(hours=24)
        campaigns = campaigns = Campaign.objects.filter(timestamp__gte=last_24_hours).distinct()
        serializer = CampaignSerializer(campaigns, many=True)

        # 2. Flatten JSON: campaign + metrics
        flat_data_list = []
        for campaign_data in serializer.data:
            flat_data = {
                **{k: v for k, v in campaign_data.items() if k != 'metrics'},
                **campaign_data.get('metrics', {})
            }
            flat_data_list.append(flat_data)
        df = pd.DataFrame(flat_data_list)

        if df.empty:
            return Response({
                "success": False,
                "message": "No campaign data found in the last 24 hours."
            })

        # 3. Create 8 DataFrames by state and drop duplicate campaign_id in each
        grouped_dfs = []
        df['state'] = pd.to_numeric(df.get('state', -1), errors='coerce').fillna(-1).astype(int)
        for i in range(8):
            state_df = df[df['state'] == i].copy()
            state_df = state_df.drop_duplicates(subset='campaign_id', keep='last').reset_index(drop=True)
            grouped_dfs.append(state_df)

        # 4. Combine all 8 DataFrames
        combined_df = pd.concat(grouped_dfs, ignore_index=True)

        # 5. Ensure numeric metric fields
        metric_fields = [
            'cost', 'revenue', 'profit', 'clicks', 'conversions',
            'conversion_rate', 'roi', 'cpc', 'profit_margin'
        ]
        for field in metric_fields:
            combined_df[field] = pd.to_numeric(combined_df.get(field, 0), errors='coerce').fillna(0)

        # 6. Average metrics per campaign
        avg_df = combined_df.groupby(['campaign_id', 'campaign_name'], as_index=False)[metric_fields].mean()

        if avg_df.empty:
            return Response({
                "success": False,
                "message": "No campaign data with valid metrics."
            })

        # 7. Run recommendation model
        scaler, dbscan, features = load_model()
        processed_df = preprocess(avg_df.copy(), features)
        X = processed_df[features].copy()
        X = scaler.transform(X)
        cluster_labels = dbscan.fit_predict(X)
        recommendations = map_clusters_to_recommendations(processed_df, cluster_labels)

        # 8. Final response with all fields
        output = []
        for row, rec in zip(avg_df.to_dict(orient="records"), recommendations):
            output.append({
                "campaign_id": row["campaign_id"],
                "campaign": row["campaign_name"],
                "recommendation": rec,
                "cost": row["cost"],
                "revenue": row["revenue"],
                "profit": row["profit"],
                "clicks": row["clicks"],
                "conversions": row["conversions"],
                "conversion_rate": row["conversion_rate"],
                "roi": row["roi"],
                "cpc": row["cpc"],
                "profit_margin": row["profit_margin"]
            })

        return Response({
            "success": True,
            "recommendations": output
        })