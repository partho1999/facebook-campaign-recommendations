import os
import joblib
import numpy as np
import pandas as pd
from django.conf import settings


MODEL_BUNDLE_PATH = os.path.join(settings.MEDIA_ROOT, 'dbscan_model.pkl')


def load_model():
    bundle = joblib.load(MODEL_BUNDLE_PATH)
    return bundle['scaler'], bundle['dbscan'], bundle['features']

def feature_engineering(df):
    if 'clicks' in df.columns:
        df['log_clicks'] = np.log1p(df['clicks'])
    if 'revenue' in df.columns and 'cost' in df.columns:
        df['revenue_to_cost'] = df['revenue'] / (df['cost'] + 1e-6)
    return df

def preprocess(df, features):
    df = df.fillna(0)
    # Ensure required columns exist
    for col in ['conversions', 'clicks', 'profit', 'cost', 'revenue']:
        if col not in df.columns:
            df[col] = 0
    df['conversion_rate'] = df['conversions'] / df['clicks'].replace(0, 1)
    df['roi'] = df['profit'] / df['cost'].replace(0, 1)
    df['cpc'] = df['cost'] / df['clicks'].replace(0, 1)
    df['profit_margin'] = df['profit'] / df['revenue'].replace(0, 1)
    df = feature_engineering(df)
    for col in features:
        if col not in df.columns:
            df[col] = 0
    df = df.replace([np.inf, -np.inf], 0)
    return df

def map_clusters_to_recommendations(df, cluster_labels):
    df = df.copy()
    df['dbscan_cluster'] = cluster_labels

    def recommend(row):
        roi = row.get('roi_confirmed', row.get('roi', 0))
        profit = row.get('profit', 0)
        cost = row.get('cost', 0)
        conversions = row.get('conversions', 0)
        revenue = row.get('revenue', 0)
        cluster = row['dbscan_cluster']

        # Absolute zero case
        if profit == 0.0 and roi == 0.0 and cost == 0.0 and conversions == 0 and revenue == 0:
            return 'UNDER OBSERVATION'
        
        # ROI-based logic
        if roi < 0:
            return 'PAUSE'
        elif roi > 100:
            return 'INCREASE BUDGET'
        elif roi > 50:
            return 'INCREASE BUDGET'
        elif roi > 20:
            return 'INCREASE BUDGET'
        elif 0 < roi <= 20:
            return 'KEEP RUNNING'

        # Fallback cluster + behavior logic
        if profit < -1:
            return 'PAUSE'
        if cluster == -1 and cost > 10 and roi < 0:
            return 'PAUSE'
        if cost > 5 and roi > 50:
            return 'INCREASE BUDGET'
        if cluster == 1 or roi >= 0:
            return 'INCREASE BUDGET'
        if cluster == -1 or roi < -10:
            return 'PAUSE'
        if cluster == 0 and -10 <= roi < 0:
            return 'OPTIMIZE'

        # ROI drop day-over-day logic (requires day-by-day comparison)
        # Note: You must pass prior-day ROI values in row if this is to be used
        if row.get('roi_day1') and row.get('roi_day2'):
            if row['roi_day1'] > 50 and row['roi_day2'] < 10:
                return 'DECREASE TO DAY 1 BUDGET'

        return 'REVIEW'

    return [recommend(row).strip().upper() for _, row in df.iterrows()]