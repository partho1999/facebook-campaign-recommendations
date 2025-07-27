import os
import pandas as pd
import numpy as np
import joblib
import json
import django
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
        print(f"📦 Loading trained DBSCAN model from {self.model_path}...")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        self.model_bundle = joblib.load(self.model_path)
        self.scaler = self.model_bundle['scaler']
        self.dbscan = self.model_bundle['dbscan']
        self.features = self.model_bundle['features']
        
        print("✅ Model loaded successfully!")
        print(f"   📊 Features: {self.features}")
        print(f"   🎯 Best parameters: {self.model_bundle['best_params']}")
        print(f"   📅 Training timestamp: {self.model_bundle['training_timestamp']}")
        
    def preprocess_data(self, df):
        print("\n🔧 Preprocessing data for inference...")
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
        
        print(f"✅ Data preprocessed. Shape: {df.shape}")
        return df
    
    def extract_features(self, df):
        print("\n📊 Extracting features...")
        feature_data = {}
        for feature in self.features:
            if feature in df.columns:
                feature_data[feature] = df[feature]
            else:
                print(f"⚠️ Feature '{feature}' not found, using zeros")
                feature_data[feature] = np.zeros(len(df))
        
        X = pd.DataFrame(feature_data)
        print(f"✅ Features extracted. Shape: {X.shape}")
        print(f"   📋 Features: {list(X.columns)}")
        return X
    
    def predict_clusters(self, X):
        print("\n🎯 Predicting clusters...")
        X_scaled = self.scaler.transform(X)
        labels = self.dbscan.fit_predict(X_scaled)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = list(labels).count(-1)
        
        print(f"✅ Clustering completed:")
        print(f"   📊 Number of clusters: {n_clusters}")
        print(f"   🔍 Noise points: {n_noise}")
        print(f"   📈 Noise ratio: {n_noise/len(labels)*100:.1f}%")
        return labels
    
    def generate_recommendations(self, df, labels):
        print("\n💡 Generating campaign recommendations...")
        df_result = df.copy()
        df_result['cluster'] = labels

        def get_recommendation(row):
            cluster = row['cluster']
            roi = row.get('roi_confirmed', 0)
            cost = row.get('cost', 0)
            revenue = row.get('revenue', 0)
            clicks = row.get('clicks', 0)
            # Real-time recommendation logic
            if cluster == -1:  # Noise/Outliers
                if roi > 50:
                    return "INCRESE BUDGET", "Outlier with high ROI - monitor for scaling", 2
                elif roi > 0:
                    return "INCRESE BUDGET", "Outlier with positive ROI - watch performance", 6
                else:
                    return "PAUSE_IMMEDIATELY", "Outlier with poor performance - stop spending", 1
            elif cluster in [4, 5]:  # High performance clusters (ROI > 1000%)
                if cost > 0 and roi > 500:
                    return "INCRESE_BUDGET_AGGRESSIVE", "Exceptional performance - increase budget 200%", 1
                else:
                    return "INCRESE_BUDGET_AGGRESSIVE", "High performance - increase budget 50%", 2
            elif cluster == 0:  # Medium performance (ROI ~-35%)
                if clicks > 100 and roi > -20:
                    return "OPTIMIZE_TARGETING", "Good traffic, optimize for better conversion", 4
                elif cost < 50:
                    return "TEST_SCALING", "Low cost campaign - test small budget increase", 5
                else:
                    return "REDUCE_BUDGET", "Underperforming", 3
            elif cluster == 1:  # Lower medium performance (ROI ~-67%)
                if clicks > 50:
                    return "OPTIMIZE_CREATIVE", "Traffic available - test new creatives", 4
                else:
                    return "REDUCE_BUDGET", "Poor performance - reduce budget by 50%", 3
            elif cluster in [2, 3, 6]:  # Poor performance clusters (ROI ~-100%)
                if cost > 100:
                    return "PAUSE_IMMEDIATELY", "High spend, poor ROI - stop immediately", 1
                elif cost > 20:
                    return "PAUSE_TODAY", "Moderate spend, poor ROI - pause within hours", 2
                else:
                    return "RESTRUCTURE", "Low spend - completely restructure campaign", 5
            else:
                return "MANUAL_REVIEW", "Unknown pattern - requires manual analysis", 7
        # Apply recommendations
        recommendations = df_result.apply(get_recommendation, axis=1)
        df_result['recommendation'] = [rec[0] for rec in recommendations]
        df_result['reason'] = [rec[1] for rec in recommendations]
        df_result['priority'] = [rec[2] for rec in recommendations]
        # Add urgency flags
        df_result['urgent'] = df_result['priority'] <= 2
        df_result['action_needed'] = df_result['priority'] <= 4
        # Sort by priority and potential impact
        df_result['potential_impact'] = df_result['cost'] * abs(df_result['roi_confirmed'])
        df_result = df_result.sort_values(['priority', 'potential_impact'], ascending=[True, False])
        return df_result
    
    def analyze_recommendations(self, df_result):
        print("\n📈 Recommendation Analysis:")
        rec_summary = df_result['recommendation'].value_counts()
        print("\n🎯 Recommendation Summary:")
        for rec_type, count in rec_summary.items():
            percentage = (count / len(df_result)) * 100
            print(f"   {rec_type}: {count:,} campaigns ({percentage:.1f}%)")
        
        cluster_summary = df_result.groupby('cluster').agg({
            'roi_confirmed': ['mean', 'count'],
            'cost': 'sum',
            'revenue': 'sum'
        }).round(2)
        print("\n📊 Cluster Performance Summary:")
        print(cluster_summary)
        
        high_priority = df_result[df_result['priority'] <= 2]
        if not high_priority.empty:
            print(f"\n🚨 High Priority Actions ({len(high_priority)} campaigns):")
            for _, row in high_priority.head(10).iterrows():
                campaign_name = row.get('campaign', f"Campaign {row.get('campaign_id', 'Unknown')}")
                print(f"   • {row['recommendation']}: {campaign_name[:50]}...")
                print(f"     ROI: {row.get('roi_confirmed', 0):.1f}%, Cost: ${row.get('cost', 0):.2f}")
    
    def save_results(self, df_result, output_prefix='inference_results'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = f"{output_prefix}.csv"
        df_result.to_csv(csv_path, index=False)
        json_path = f"{output_prefix}.json"
        df_result.to_json(json_path, orient='records', indent=2)
        
        print(f"\n💾 Results saved:")
        print(f"   📊 {csv_path}")
        print(f"   📄 {json_path}")
        return csv_path, json_path
    
    
        
    def run_inference(self, data_source, save_results=True):
        print("🚀 Starting DBSCAN Campaign Inference")
        print("=" * 50)
        
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
        
        print(f"📂 Data loaded. Shape: {df.shape}")
        df_processed = self.preprocess_data(df)
        X = self.extract_features(df_processed)
        labels = self.predict_clusters(X)
        df_result = self.generate_recommendations(df_processed, labels)
        self.analyze_recommendations(df_result)
        
        if save_results:
            return self.save_results(df_result)
        else:
            return None, None


def main():
    """Main function to run inference"""
    model_path = os.path.join(settings.MEDIA_ROOT, 'dbscan_model_bundle_latest.pkl')
    if not os.path.exists(model_path):
        print(f"❌ Model file not found: {model_path}")
        print("Please run the DBSCAN trainer first to generate the model.")
        return

    data_path =os.path.join(settings.MEDIA_ROOT, 'preprocess_data.json')
    if not os.path.exists(data_path):
        print(f"❌ Data file not found: {data_path}")
        print("Please run the downloader script first to generate the data.")
        return

    try:
        inference = DBSCANCampaignInference(model_path)
        csv_path, json_path = inference.run_inference(data_path, save_results=True)

        print(f"\n🎯 Next Steps:")
        print(f"   1. Review high-priority recommendations")
        print(f"   2. Implement suggested campaign actions")
        print(f"   3. Monitor performance changes")
        print(f"   4. Re-run inference periodically for updated recommendations")

        # Return saved JSON content
        with open(json_path, 'r', encoding='utf-8') as f:
            saved_json = json.load(f)
        return saved_json

    except Exception as e:
        print(f"❌ Error during inference: {str(e)}")
        raise

# Uncomment to run directly
# if __name__ == "__main__":
#     main()
