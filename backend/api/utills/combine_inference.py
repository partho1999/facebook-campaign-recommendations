import os
import json
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
import warnings
from django.conf import settings

warnings.filterwarnings('ignore')


class DBSCANCampaignInference:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(settings.MEDIA_ROOT, 'dbscan_model_bundle_latest.pkl')

        self.model_path = model_path
        self.model_bundle = None
        self.scaler = None
        self.dbscan = None
        self.features = None
        self.load_model()

    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        self.model_bundle = joblib.load(self.model_path)
        self.scaler = self.model_bundle['scaler']
        self.dbscan = self.model_bundle['dbscan']
        self.features = self.model_bundle['features']

    def preprocess_data(self, df):
        numeric_cols = ['cost', 'revenue', 'profit', 'clicks', 'campaign_unique_clicks',
                        'conversions', 'roi_confirmed', 'lp_clicks', 'cr', 'lp_ctr']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.fillna(0)
        if 'revenue' in df.columns and 'cost' in df.columns:
            df['revenue_to_cost_ratio'] = df['revenue'] / (df['cost'] + 1e-6)
        if 'conversions' in df.columns and 'clicks' in df.columns:
            df['conversion_rate'] = df['conversions'] / (df['clicks'] + 1e-6)
        if 'profit' in df.columns and 'cost' in df.columns:
            df['profit_margin'] = df['profit'] / (df['cost'] + 1e-6)
        return df

    def extract_features(self, df):
        feature_data = {}
        for feature in self.features:
            if feature in df.columns:
                feature_data[feature] = df[feature]
            else:
                feature_data[feature] = np.zeros(len(df))
        X = pd.DataFrame(feature_data)
        return X

    def predict_clusters(self, X):
        X_scaled = self.scaler.transform(X)
        labels = self.dbscan.fit_predict(X_scaled)
        return labels

    def generate_recommendations(self, df, labels):
        df_result = df.copy()
        df_result['cluster'] = labels

        def get_recommendation(row):
            cluster = row['cluster']
            roi = row.get('roi_confirmed', 0)
            cost = row.get('cost', 0)
            increase_pct = None
            if cost < 5:
                return "KEEP_RUNNING", "Insufficient spend (<$5)", "Wait for more data before making changes", 0
            if cluster == -1:
                if roi > 0:
                    increase_pct = min(200, roi / 5)
                    increase_pct = round(increase_pct)
                    return "INCREASE_BUDGET", f"Outlier ROI {roi:.1f}%", f"Increase budget by {increase_pct}%", increase_pct
                elif roi > -50:
                    increase_pct = min(50, abs(roi) / 2)
                    increase_pct = round(increase_pct)
                    return "OPTIMIZE", f"Outlier with slightly negative ROI {roi:.1f}%", f"Decrease budget by {increase_pct}%", -increase_pct
                else:
                    return "PAUSE", f"Outlier with poor ROI {roi:.1f}%", "Pause campaign immediately", 0
            if cluster in [4, 5]:
                if roi > 0:
                    increase_pct = min(200, roi / 5)
                    increase_pct = round(increase_pct)
                    return "INCREASE_BUDGET", f"High ROI {roi:.1f}%", f"Increase budget by {increase_pct}%", increase_pct
                else:
                    return "OPTIMIZE", f"High performance cluster with no ROI {roi:.1f}%", "Improve ad quality or landing page", 0
            if cluster in [0, 1]:
                if roi > 0:
                    return "OPTIMIZE", f"Moderate ROI {roi:.1f}%", "Test creatives and refine targeting", 0
                else:
                    increase_pct = min(50, abs(roi) / 2)
                    increase_pct = round(increase_pct)
                    return "REDUCE_BUDGET", f"Negative ROI {roi:.1f}%", f"Reduce budget by {increase_pct}%", -increase_pct
            if cluster in [2, 3, 6]:
                if cost > 100:
                    return "PAUSE", f"High spend (${cost:.0f}) with poor ROI {roi:.1f}%", "Pause immediately", 0
                else:
                    return "RESTRUCTURE", f"Low spend with poor ROI {roi:.1f}%", "Restructure campaign from scratch", 0
            return "REVIEW", "Unknown cluster", "Manual review required", 0

        recommendations = df_result.apply(get_recommendation, axis=1)
        df_result['recommendation'] = [r[0] for r in recommendations]
        df_result['reason'] = [r[1] for r in recommendations]
        df_result['suggestion'] = [r[2] for r in recommendations]
        df_result['budget_change_pct'] = [r[3] if r[3] is not None else 0 for r in recommendations]
        df_result['raw_budget_change_pct'] = df_result['budget_change_pct']

        priority_map = {
            'PAUSE': 1,
            'INCREASE_BUDGET': 2,
            'REDUCE_BUDGET': 3,
            'OPTIMIZE': 4,
            'RESTRUCTURE': 5,
            'KEEP_RUNNING': 6,
            'MONITOR_CLOSELY': 7,
            'REVIEW': 8
        }
        df_result['priority'] = df_result['recommendation'].map(priority_map).fillna(99)
        df_result = df_result.sort_values(['priority', 'roi_confirmed'], ascending=[True, False])
        return df_result

    def analyze_recommendations(self, df_result):
        pass

    def save_results(self, df_result, output_prefix='inference_results'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = f"{output_prefix}.csv"
        df_result.to_csv(csv_path, index=False)
        json_path = f"{output_prefix}.json"
        df_result.to_json(json_path, orient='records', indent=2)
        return csv_path, json_path

    def run_inference(self, data_source, save_results=True):
        if isinstance(data_source, dict):
            df = pd.DataFrame(data_source['adset'])
        elif isinstance(data_source, list):
            df = pd.DataFrame(data_source)
        else:
            raise ValueError("data_source should be dict with 'adset' key or list of adsets")
        df_processed = self.preprocess_data(df)
        X = self.extract_features(df_processed)
        labels = self.predict_clusters(X)
        df_result = self.generate_recommendations(df_processed, labels)
        self.analyze_recommendations(df_result)
        if save_results:
            self.save_results(df_result)
        return df_result


def enrich_campaign_data(input_data, model_path=None):
    inference = DBSCANCampaignInference(model_path=model_path)
    df_result = inference.run_inference(input_data, save_results=False)
    adsets_with_recs = df_result.to_dict(orient='records')

    budgeted_adsets = [a for a in adsets_with_recs if a.get('cost', 0) >= 5]
    total_budgeted = len(budgeted_adsets)

def enrich_campaign_data(input_data, model_path=None):
    inference = DBSCANCampaignInference(model_path=model_path)
    df_result = inference.run_inference(input_data, save_results=False)
    adsets_with_recs = df_result.to_dict(orient='records')

    budgeted_adsets = [a for a in adsets_with_recs if a.get('cost', 0) >= 5]
    total_budgeted = len(budgeted_adsets)

    def calculate_budget_change_pct(adset):
        roi = adset.get('roi_confirmed', 0)
        rec = adset.get('recommendation', '')
        if rec == "INCREASE_BUDGET":
            increase_pct = round(min(200, roi / 5))
        elif rec in ["REDUCE_BUDGET", "OPTIMIZE"]:
            if roi < 0:
                increase_pct = -round(min(50, abs(roi) / 2))
            else:
                increase_pct = 0
        else:
            increase_pct = 0
        return increase_pct

    if total_budgeted > 0:
        rec_counts = {}
        for a in budgeted_adsets:
            rec = a.get('recommendation')
            rec_counts[rec] = rec_counts.get(rec, 0) + 1

        majority_rec = max(rec_counts.items(), key=lambda x: x[1])[0]

        recalculated_budget_changes = [calculate_budget_change_pct(a) for a in budgeted_adsets]
        average_budget_change_pct = round(np.mean(recalculated_budget_changes))

        average_roi = input_data.get("average_roi", 0)
        if average_roi > 0:
            recommendation_percentage = round(min(200, average_roi / 5))
        else:
            recommendation_percentage = -round(min(50, abs(average_roi) / 2))

        total_roi = sum(a.get('roi_confirmed', 0) for a in budgeted_adsets)
        if total_roi > 0:
            total_budget_change_pct_sum = round(min(200, total_roi / 5))
        else:
            total_budget_change_pct_sum = -round(min(50, abs(total_roi) / 2))

        # Override recommendation if recommendation_percentage is negative
        if recommendation_percentage < 0:
            majority_rec = "PAUSE"
            # Optional: you might want to also force recommendation_percentage positive 0 or abs here or keep as is

    else:
        majority_rec = "KEEP_RUNNING"
        average_budget_change_pct = 0
        recommendation_percentage = 0
        total_budget_change_pct_sum = 0.0

    output = {
        "id": input_data.get("id"),
        "sub_id_6": input_data.get("sub_id_6"),
        "sub_id_3": input_data.get("sub_id_3"),
        "total_cost": input_data.get("total_cost"),
        "total_revenue": input_data.get("total_revenue"),
        "total_profit": input_data.get("total_profit"),
        "total_clicks": input_data.get("total_clicks"),
        "average_cpc": input_data.get("average_cpc"),
        "average_roi": input_data.get("average_roi"),
        "average_conversion_rate": input_data.get("average_conversion_rate"),
        "recommendation": majority_rec,
        "recommendation_percentage": recommendation_percentage,
        "total_budget_change_pct_sum": total_budget_change_pct_sum,
        "adset": adsets_with_recs
    }
    return output


