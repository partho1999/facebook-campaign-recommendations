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
import os
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
            API_KEY = os.getenv('API_KEY')
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
                    "Api-Key": API_KEY,
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
        try:
            now = timezone.now()
            last_24_hours = now - timedelta(hours=24)

            grouped_dfs = []
            for i in range(8):
                start_time = last_24_hours + timedelta(hours=3 * i)
                end_time = start_time + timedelta(hours=3)

                campaigns = Campaign.objects.filter(
                    timestamp__gte=start_time,
                    timestamp__lt=end_time
                )
                serializer = CampaignSerializer(campaigns, many=True)
                flat_data = []
                for item in serializer.data:
                    metrics = item.get('metrics', {})
                    flat_data.append({
                        'campaign_id': item['campaign_id'],
                        'campaign_name': item.get('campaign_name', ''),
                        'cost': float(metrics.get('cost', 0.0)),
                        'revenue': float(metrics.get('revenue', 0.0)),
                        'clicks': int(metrics.get('clicks', 0)),
                        'conversions': int(metrics.get('conversions', 0)),
                    })

                df = pd.DataFrame(flat_data)

                if not df.empty:
                    df = df.drop_duplicates(subset=['campaign_id', 'campaign_name'])
                    grouped = df.groupby(['campaign_id', 'campaign_name'], as_index=False).agg({
                        'cost': 'sum',
                        'revenue': 'sum',
                        'clicks': 'sum',
                        'conversions': 'sum',
                    })
                    grouped_dfs.append(grouped)

            non_empty_dfs = [df for df in grouped_dfs if not df.empty]

            if not non_empty_dfs:
                return Response({
                    'success': True,
                    'recommendations': []
                }, status=status.HTTP_200_OK)

            total_24h_df = pd.concat(non_empty_dfs)
            total_24h_df = total_24h_df.groupby(['campaign_id', 'campaign_name'], as_index=False).sum()

            total_24h_df['profit'] = total_24h_df['revenue'] - total_24h_df['cost']
            total_24h_df['roi'] = total_24h_df.apply(lambda r: (r['revenue'] / r['cost']) if r['cost'] > 0 else 0.0, axis=1)
            total_24h_df['conversion_rate'] = total_24h_df.apply(lambda r: (r['conversions'] / r['clicks']) if r['clicks'] > 0 else 0.0, axis=1)
            total_24h_df['cpc'] = total_24h_df.apply(lambda r: (r['cost'] / r['clicks']) if r['clicks'] > 0 else 0.0, axis=1)
            total_24h_df['profit_margin'] = total_24h_df.apply(lambda r: (r['profit'] / r['revenue']) if r['revenue'] > 0 else 0.0, axis=1)

            scaler, dbscan, features = load_model()

            processed_df = preprocess(total_24h_df.copy(), features)
            X = scaler.transform(processed_df[features])

            cluster_labels = dbscan.fit_predict(X)

            # **Important**: map clusters to recommendations exactly like before
            recommendations = map_clusters_to_recommendations(processed_df, cluster_labels)

            total_24h_df['recommendation'] = recommendations

            result = total_24h_df.to_dict(orient='records')

            return Response({
                'success': True,
                'recommendations': result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


