import requests
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
import numpy as np
from django.utils import timezone
from scipy.stats import linregress
from api.models import Campaign
from api.utills.utills import load_model, preprocess, map_clusters_to_recommendations
from django.conf import settings
from threading import Lock
from api.serializers import CampaignSerializer

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
            api_key = request.GET.get('api_key', 'c1da605a864e6c74beb71d3a713e019c')
            base_url = request.GET.get('base_url', 'https://tracktheweb.online')
            hours_back = int(request.GET.get('hours_back', 24))

            time_ranges = [hours_back]
            final_output = []

            for time_range in time_ranges:
                end_date = datetime.now()
                start_date = end_date - timedelta(hours=time_range)

                payload = {
                    "range": {
                        "from": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "to": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "timezone": "Europe/Amsterdam"
                    },
                    "columns": [
                        "sub_id_3", "campaign", "campaign_id", "cost", "revenue", "profit",
                        "clicks", "campaign_unique_clicks", "conversions", "roi_confirmed",
                        "datetime", "lp_clicks", "cr", "lp_ctr"
                    ],
                    "metrics": [
                        "clicks", "cost", "campaign_unique_clicks", "conversions", "roi_confirmed"
                    ],
                    "grouping": ["campaign_id"],
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
                    f"{base_url}/admin_api/v1/report/build",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                rows = data.get('rows', [])

                if not rows:
                    continue

                # # Print unique campaign_id values and their count
                # unique_campaign_ids = set(row.get('campaign_id') for row in rows if 'campaign_id' in row)
                # print(f"Number of unique campaign_id: {len(unique_campaign_ids)}")
                # print(f"Unique campaign_id values: {unique_campaign_ids}")

                df = pd.DataFrame(rows)

                required_cols = [
                    'campaign_id', 'campaign', 'cost', 'revenue', 'profit',
                    'clicks', 'conversions', 'conversion_rate', 'roi',
                    'cpc', 'profit_margin'
                ]
                for col in required_cols:
                    if col not in df.columns:
                        df[col] = 0

                # Keep only the last occurrence of each campaign_id in the DataFrame
                df = df.drop_duplicates(subset='campaign_id', keep='last').reset_index(drop=True)


                if df.empty:
                    continue  # ✅ All data already processed

                # Increment and cycle state 0-7 ONCE per request
                with settings.CAMPAIGN_STATE_LOCK:
                    state = settings.CAMPAIGN_STATE
                    settings.CAMPAIGN_STATE = (settings.CAMPAIGN_STATE + 1) % 8

                df = preprocess(df, features)
                X = df[features].copy()
                X = scaler.transform(X)
                cluster_labels = dbscan.fit_predict(X)
                recommendations = map_clusters_to_recommendations(df, cluster_labels)

                output = []
                for i, row in df.iterrows():
                    campaign_id = row.get('campaign_id', f'campaign_{i}')
                    campaign_name = row.get('campaign', f'campaign_{i}')
                    cluster = int(cluster_labels[i])
                    recommendation = recommendations[i]
                    timestamp = datetime.now()

                    Campaign.objects.create(
                        campaign_id=campaign_id,
                        campaign_name=campaign_name,
                        cluster=cluster,
                        recommendation=recommendation,
                        cost=row['cost'],
                        revenue=row['revenue'],
                        profit=row['profit'],
                        clicks=row['clicks'],
                        conversions=row['conversions'],
                        conversion_rate=row['conversion_rate'],
                        roi=row['roi'],
                        cpc=row['cpc'],
                        profit_margin=row['profit_margin'],
                        timestamp=timestamp,
                        state=state
                    )

                    output.append({
                        'campaign_id': campaign_id,
                        'campaign_name': campaign_name,
                        'cluster': cluster,
                        'recommendation': recommendation,
                        'metrics': {
                            'cost': row['cost'],
                            'revenue': row['revenue'],
                            'profit': row['profit'],
                            'clicks': row['clicks'],
                            'conversions': row['conversions'],
                            'conversion_rate': row['conversion_rate'],
                            'roi': row['roi'],
                            'cpc': row['cpc'],
                            'datetime': row['datetime'],
                            'profit_margin': row['profit_margin']
                        },
                        'timestamp': timestamp.isoformat(),
                        'state': state
                    })

                rec_counts = {}
                for rec in recommendations:
                    key = rec.strip().upper()
                    rec_counts[key] = rec_counts.get(key, 0) + 1

                summary = {
                    'total_campaigns': len(output),
                    'recommendation_counts': rec_counts,
                    'date_range': {
                        'from': start_date.strftime("%Y-%m-%d %H:%M:%S"),
                        'to': end_date.strftime("%Y-%m-%d %H:%M:%S")
                    },
                    'timestamp': datetime.now().isoformat()
                }

                final_output.append({
                    'range': f'{time_range}h',
                    'recommendations': output,
                    'summary': summary
                })

            return Response({'success': True, 'data': final_output}, status=status.HTTP_200_OK)

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