import os
import pandas as pd
import numpy as np
import joblib
import json
from django.conf import settings
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')
class DBSCANCampaignInference:
    def __init__(self, model_path='dbscan_model_bundle_latest.pkl'):
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
                print(f":warning: Feature '{feature}' not found, using zeros")
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
            increase_pct = None  # Default value for budget change

            if cost < 5:
                return "KEEP_RUNNING", "Insufficient spend (<$5)", "Wait for more data before making changes", None

            # Outliers / noise
            if cluster == -1:
                if roi > 0:
                    increase_pct = min(200, roi / 5)
                    return "INCREASE_BUDGET", f"Outlier ROI {roi:.1f}%", f"Increase budget by {increase_pct:.0f}%", increase_pct
                elif roi > -50:
                    increase_pct = min(50, abs(roi) / 2)
                    return "OPTIMIZE", f"Outlier with slightly negative ROI {roi:.1f}%", f"Decrease budget by {increase_pct:.0f}%", -increase_pct
                else:
                    return "PAUSE", f"Outlier with poor ROI {roi:.1f}%", "Pause campaign immediately", None

            # High performance clusters
            if cluster in [4, 5]:
                if roi > 0:
                    increase_pct = min(200, roi / 5)
                    return "INCREASE_BUDGET", f"High ROI {roi:.1f}%", f"Increase budget by {increase_pct:.0f}%", increase_pct
                else:
                    return "OPTIMIZE", f"High performance cluster with no ROI {roi:.1f}%", "Improve ad quality or landing page", None

            # Medium performance clusters
            if cluster in [0, 1]:
                if roi > 0:
                    return "OPTIMIZE", f"Moderate ROI {roi:.1f}%", "Test creatives and refine targeting", None
                else:
                    increase_pct = min(50, abs(roi) / 2)
                    return "REDUCE_BUDGET", f"Negative ROI {roi:.1f}%", f"Reduce budget by {increase_pct:.0f}%", -increase_pct

            # Poor performance clusters
            if cluster in [2, 3, 6]:
                if cost > 100:
                    return "PAUSE", f"High spend (${cost:.0f}) with poor ROI {roi:.1f}%", "Pause immediately", None
                else:
                    return "RESTRUCTURE", f"Low spend with poor ROI {roi:.1f}%", "Restructure campaign from scratch", None

            # Fallback
            return "REVIEW", "Unknown cluster", "Manual review required", None

        # Apply recommendations
        recommendations = df_result.apply(get_recommendation, axis=1)

        # Unpack returned values into separate columns
        df_result['recommendation'] = [rec[0] for rec in recommendations]
        df_result['reason'] = [rec[1] for rec in recommendations]
        df_result['suggestion'] = [rec[2] for rec in recommendations]
        df_result['budget_change_pct'] = [round(rec[3]) if rec[3] is not None else 0 for rec in recommendations]  # Default to 0

        # Priority map and sorting
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

    def add_cpc_level(self, df, cpc_col='cpc', geo_col='geo'):
        # Normalize columns to lowercase for safety
        df.columns = [col.lower() for col in df.columns]
        cpc_col = cpc_col.lower()
        geo_col = geo_col.lower()
        if cpc_col not in df.columns or geo_col not in df.columns:
            raise ValueError(f"Columns '{cpc_col}' and '{geo_col}' must be present in dataframe")
        geo_stats = df.groupby(geo_col)[cpc_col].agg(['mean', 'std']).rename(columns={'mean': 'mean_cpc', 'std': 'std_cpc'})
        df = df.merge(geo_stats, left_on=geo_col, right_index=True, how='left')
        df['std_cpc'] = df['std_cpc'].replace(0, 1e-6)
        df['z_score'] = (df[cpc_col] - df['mean_cpc']) / df['std_cpc']
        def label_cpc(z):
            if pd.isna(z):
                return 'INSUFFICIENT_DATA'  # Optional: can also be 'STANDARD' or another label
            elif z < -1:
                return 'LOW'
            elif z > 1:
                return 'HIGH'
            else:
                return 'STANDARD'

        df['cpc_rate'] = df['z_score'].apply(label_cpc)
        df.drop(columns=['mean_cpc', 'std_cpc', 'z_score'], inplace=True)
        return df
    def analyze_recommendations(self, df_result):
        rec_summary = df_result['recommendation'].value_counts()
        # Uncomment prints if needed
        # for rec_type, count in rec_summary.items():
        #     percentage = (count / len(df_result)) * 100
        #     print(f"   {rec_type}: {count:,} campaigns ({percentage:.1f}%)")
        cluster_summary = df_result.groupby('cluster').agg({
            'roi_confirmed': ['mean', 'count'],
            'cost': 'sum',
            'revenue': 'sum'
        }).round(2)
        # print(cluster_summary)
        high_priority = df_result[df_result['priority'] <= 2]
        if not high_priority.empty:
            # print(f"\n:rotating_light: High Priority Actions ({len(high_priority)} campaigns):")
            for _, row in high_priority.head(10).iterrows():
                campaign_name = row.get('campaign', f"Campaign {row.get('campaign_id', 'Unknown')}")
                # print(f"   • {row['recommendation']}: {campaign_name[:50]}...")
                # print(f"     ROI: {row.get('roi_confirmed', 0):.1f}%, Cost: ${row.get('cost', 0):.2f}")
    def save_results(self, df_result, output_prefix='inference_results'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = f"{output_prefix}.csv"
        df_result.to_csv(csv_path, index=False)
        json_path = f"{output_prefix}.json"
        df_result.to_json(json_path, orient='records', indent=2)
        return csv_path, json_path
    def run_inference(self, data_source, save_results=True):
        if isinstance(data_source, str):
            if data_source.endswith('.json'):
                with open(data_source, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'rows' in data:
                    df = pd.DataFrame(data['rows'])
                else:
                    df = pd.DataFrame(data)
            elif data_source.endswith('.csv'):
                df = pd.read_csv(data_source)
            else:
                raise ValueError("Unsupported file format. Use .json or .csv")
        else:
            df = data_source.copy()
        df_processed = self.preprocess_data(df)
        X = self.extract_features(df_processed)
        labels = self.predict_clusters(X)
        df_result = self.generate_recommendations(df_processed, labels)
        # Add CPC level here, assuming 'cpc' and 'geo' columns present
        df_result = self.add_cpc_level(df_result, cpc_col='cpc', geo_col='geo')
        self.analyze_recommendations(df_result)
        if save_results:
            return self.save_results(df_result)
        else:
            return None, None
def main(data_path):
    """Main function to run inference"""
    model_path = os.path.join(settings.MEDIA_ROOT, 'dbscan_model_bundle_latest.pkl')
    if not os.path.exists(model_path):
        return
    # data_path = os.path.join(settings.MEDIA_ROOT, 'preprocess_data.json')
    if not os.path.exists(data_path):
        return
    try:
        inference = DBSCANCampaignInference(model_path)
        csv_path, json_path = inference.run_inference(data_path, save_results=True)
        with open(json_path, 'r', encoding='utf-8') as f:
            saved_json = json.load(f)
        return saved_json
    except Exception as e:
        raise
# Uncomment to run directly
# if __name__ == "__main__":
#     main()




# import os
# import pandas as pd
# import numpy as np
# import joblib
# import json
# import django
# from django.conf import settings
# from datetime import datetime
# import warnings
# warnings.filterwarnings('ignore')


# class DBSCANCampaignInference:
#     def __init__(self, model_path='dbscan_model_bundle_latest.pkl'):
#         self.model_path = model_path
#         self.model_bundle = None
#         self.scaler = None
#         self.dbscan = None
#         self.features = None
#         self.load_model()
        
#     def load_model(self):
#         # print(f"📦 Loading trained DBSCAN model from {self.model_path}...")
#         if not os.path.exists(self.model_path):
#             raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
#         self.model_bundle = joblib.load(self.model_path)
#         self.scaler = self.model_bundle['scaler']
#         self.dbscan = self.model_bundle['dbscan']
#         self.features = self.model_bundle['features']
        
#         # print("✅ Model loaded successfully!")
#         # print(f"   📊 Features: {self.features}")
#         # print(f"   🎯 Best parameters: {self.model_bundle['best_params']}")
#         # print(f"   📅 Training timestamp: {self.model_bundle['training_timestamp']}")
        
#     def preprocess_data(self, df):
#         # print("\n🔧 Preprocessing data for inference...")
#         numeric_cols = ['cost', 'revenue', 'profit', 'clicks', 'campaign_unique_clicks', 
#                         'conversions', 'roi_confirmed', 'lp_clicks', 'cr', 'lp_ctr', 'cpc']
#         for col in numeric_cols:
#             if col in df.columns:
#                 df[col] = pd.to_numeric(df[col], errors='coerce')
#         df = df.fillna(0)

#         if 'revenue' in df.columns and 'cost' in df.columns:
#             df['revenue_to_cost_ratio'] = df['revenue'] / (df['cost'] + 1e-6)
#         if 'conversions' in df.columns and 'clicks' in df.columns:
#             df['conversion_rate'] = df['conversions'] / (df['clicks'] + 1e-6)
#         if 'profit' in df.columns and 'cost' in df.columns:
#             df['profit_margin'] = df['profit'] / (df['cost'] + 1e-6)
        
#         # print(f"✅ Data preprocessed. Shape: {df.shape}")
#         return df
    
#     def extract_features(self, df):
#         # print("\n📊 Extracting features...")
#         feature_data = {}
#         for feature in self.features:
#             if feature in df.columns:
#                 feature_data[feature] = df[feature]
#             else:
#                 print(f"⚠️ Feature '{feature}' not found, using zeros")
#                 feature_data[feature] = np.zeros(len(df))
        
#         X = pd.DataFrame(feature_data)
#         # print(f"✅ Features extracted. Shape: {X.shape}")
#         # print(f"   📋 Features: {list(X.columns)}")
#         return X
    
#     def predict_clusters(self, X):
#         # print("\n🎯 Predicting clusters...")
#         X_scaled = self.scaler.transform(X)
#         labels = self.dbscan.fit_predict(X_scaled)
#         n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
#         n_noise = list(labels).count(-1)
        
#         # print(f"✅ Clustering completed:")
#         # print(f"   📊 Number of clusters: {n_clusters}")
#         # print(f"   🔍 Noise points: {n_noise}")
#         # print(f"   📈 Noise ratio: {n_noise/len(labels)*100:.1f}%")
#         return labels
    
#     def generate_recommendations(self, df, labels):
#         df_result = df.copy()
#         df_result['cluster'] = labels

#         def get_recommendation(row):
#             cluster = row['cluster']
#             roi = row.get('roi_confirmed', 0)
#             cost = row.get('cost', 0)

#             if cost < 5:
#                 return "KEEP_RUNNING", "Insufficient spend (<$5)", "Wait for more data before making changes"

#             # Outliers / noise
#             if cluster == -1:
#                 if roi > 0:
#                     increase_pct = min(200, roi / 5)
#                     return "INCREASE_BUDGET", f"Outlier ROI {roi:.1f}%", f"Increase budget by {increase_pct:.0f}%"
#                 elif roi > -50:
#                     return "OPTIMIZE", f"Outlier with slightly negative ROI {roi:.1f}%", "Optimize targeting and creatives"
#                 else:
#                     return "PAUSE", f"Outlier with poor ROI {roi:.1f}%", "Pause campaign immediately"

#             # High performance clusters
#             if cluster in [4, 5]:
#                 if roi > 0:
#                     increase_pct = min(200, roi / 5)
#                     return "INCREASE_BUDGET", f"High ROI {roi:.1f}%", f"Increase budget by {increase_pct:.0f}%"
#                 else:
#                     return "OPTIMIZE", f"High performance cluster with no ROI {roi:.1f}%", "Improve ad quality or landing page"

#             # Medium performance clusters
#             if cluster in [0, 1]:
#                 if roi > 0:
#                     return "OPTIMIZE", f"Moderate ROI {roi:.1f}%", "Test creatives and refine targeting"
#                 else:
#                     decrease_pct = min(50, abs(roi) / 2)
#                     return "REDUCE_BUDGET", f"Negative ROI {roi:.1f}%", f"Reduce budget by {decrease_pct:.0f}%"

#             # Poor performance clusters
#             if cluster in [2, 3, 6]:
#                 if cost > 100:
#                     return "PAUSE", f"High spend (${cost:.0f}) with poor ROI {roi:.1f}%", "Pause immediately"
#                 else:
#                     return "RESTRUCTURE", f"Low spend with poor ROI {roi:.1f}%", "Restructure campaign from scratch"

#             # Fallback
#             return "REVIEW", "Unknown cluster", "Manual review required"

#         # Apply recommendation logic
#         recommendations = df_result.apply(get_recommendation, axis=1)
#         df_result['recommendation'] = [rec[0] for rec in recommendations]
#         df_result['reason'] = [rec[1] for rec in recommendations]
#         df_result['suggestion'] = [rec[2] for rec in recommendations]

#         # Priority mapping for sorting
#         priority_map = {
#             'PAUSE': 1,
#             'INCREASE_BUDGET': 2,
#             'REDUCE_BUDGET': 3,
#             'OPTIMIZE': 4,
#             'RESTRUCTURE': 5,
#             'KEEP_RUNNING': 6,
#             'MONITOR_CLOSELY': 7,
#             'REVIEW': 8
#         }

#         df_result['priority'] = df_result['recommendation'].map(priority_map).fillna(99)
#         df_result = df_result.sort_values(['priority', 'roi_confirmed'], ascending=[True, False])

#         return df_result




    
#     def analyze_recommendations(self, df_result):
#         # print("\n📈 Recommendation Analysis:")
#         rec_summary = df_result['recommendation'].value_counts()
#         # print("\n🎯 Recommendation Summary:")
#         for rec_type, count in rec_summary.items():
#             percentage = (count / len(df_result)) * 100
#             # print(f"   {rec_type}: {count:,} campaigns ({percentage:.1f}%)")
        
#         cluster_summary = df_result.groupby('cluster').agg({
#             'roi_confirmed': ['mean', 'count'],
#             'cost': 'sum',
#             'revenue': 'sum'
#         }).round(2)
#         # print("\n📊 Cluster Performance Summary:")
#         # print(cluster_summary)
        
#         high_priority = df_result[df_result['priority'] <= 2]
#         if not high_priority.empty:
#             # print(f"\n🚨 High Priority Actions ({len(high_priority)} campaigns):")
#             for _, row in high_priority.head(10).iterrows():
#                 campaign_name = row.get('campaign', f"Campaign {row.get('campaign_id', 'Unknown')}")
#                 # print(f"   • {row['recommendation']}: {campaign_name[:50]}...")
#                 # print(f"     ROI: {row.get('roi_confirmed', 0):.1f}%, Cost: ${row.get('cost', 0):.2f}")
    
#     def save_results(self, df_result, output_prefix='inference_results'):
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         csv_path = f"{output_prefix}.csv"
#         df_result.to_csv(csv_path, index=False)
#         json_path = f"{output_prefix}.json"
#         df_result.to_json(json_path, orient='records', indent=2)
        
#         # print(f"\n💾 Results saved:")
#         # print(f"   📊 {csv_path}")
#         # print(f"   📄 {json_path}")
#         return csv_path, json_path
    
    
        
#     def run_inference(self, data_source, save_results=True):
#         # print("🚀 Starting DBSCAN Campaign Inference")
#         # print("=" * 50)
        
#         if isinstance(data_source, str):
#             if data_source.endswith('.json'):
#                 with open(data_source, 'r', encoding='utf-8') as f:
#                     data = json.load(f)
#                 if 'rows' in data:
#                     df = pd.DataFrame(data['rows'])
#                 else:
#                     df = pd.DataFrame(data)
#             elif data_source.endswith('.csv'):
#                 df = pd.read_csv(data_source)
#             else:
#                 raise ValueError("Unsupported file format. Use .json or .csv")
#         else:
#             df = data_source.copy()
        
#         # print(f"📂 Data loaded. Shape: {df.shape}")
#         df_processed = self.preprocess_data(df)
#         X = self.extract_features(df_processed)
#         labels = self.predict_clusters(X)
#         df_result = self.generate_recommendations(df_processed, labels)
#         self.analyze_recommendations(df_result)
        
#         if save_results:
#             return self.save_results(df_result)
#         else:
#             return None, None


# def main(data_path):
#     """Main function to run inference"""
#     model_path = os.path.join(settings.MEDIA_ROOT, 'dbscan_model_bundle_latest.pkl')
#     if not os.path.exists(model_path):
#         # print(f"❌ Model file not found: {model_path}")
#         # print("Please run the DBSCAN trainer first to generate the model.")
#         return

    
#     if not os.path.exists(data_path):
#         # print(f"❌ Data file not found: {data_path}")
#         # print("Please run the downloader script first to generate the data.")
#         return

#     try:
#         inference = DBSCANCampaignInference(model_path)
#         csv_path, json_path = inference.run_inference(data_path, save_results=True)

#         # print(f"\n🎯 Next Steps:")
#         # print(f"   1. Review high-priority recommendations")
#         # print(f"   2. Implement suggested campaign actions")
#         # print(f"   3. Monitor performance changes")
#         # print(f"   4. Re-run inference periodically for updated recommendations")

#         # Return saved JSON content
#         with open(json_path, 'r', encoding='utf-8') as f:
#             saved_json = json.load(f)
#         return saved_json

#     except Exception as e:
#         # print(f"❌ Error during inference: {str(e)}")
#         raise

# # Uncomment to run directly
# # if __name__ == "__main__":
# #     main()


