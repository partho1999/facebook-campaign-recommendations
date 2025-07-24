import json
import pandas as pd
from pandas import json_normalize
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
# import matplotlib.pyplot as plt
# import seaborn as sns
import joblib  # :white_check_mark: Added to save model
# Read raw JSON
with open(r"media\New document 2.json", 'r') as f:
    data = json.load(f)
# Flatten JSON into a DataFrame
df = json_normalize(data)
# Extract the list of dictionaries from the 'rows' column
rows_list = df['rows'][0]
# Flatten the list of dictionaries into a new DataFrame
flattened_df = json_normalize(rows_list)
# Convert 'datetime' column to datetime objects
flattened_df['datetime'] = pd.to_datetime(flattened_df['datetime'])
# Extract year, month, day of the week, and hour from the 'datetime' column
flattened_df['year'] = flattened_df['datetime'].dt.year
flattened_df['month'] = flattened_df['datetime'].dt.month
flattened_df['day_of_week'] = flattened_df['datetime'].dt.dayofweek
flattened_df['hour'] = flattened_df['datetime'].dt.hour
# Create 'cost_per_click' feature, handling potential division by zero
flattened_df['cost_per_click'] = flattened_df['cost'] / flattened_df['clicks']
flattened_df['cost_per_click'] = flattened_df['cost_per_click'].replace([float('inf'), float('-inf')], 0).fillna(0)
# Perform one-hot encoding on the 'campaign' column
flattened_df = pd.get_dummies(flattened_df, columns=['campaign'], drop_first=True)
# Select relevant numerical features for clustering
numerical_features = [
    'cost', 'revenue', 'profit', 'clicks', 'campaign_unique_clicks',
    'conversions', 'roi_confirmed', 'lp_clicks', 'cr', 'lp_ctr',
    'cost_per_click'
]
X = flattened_df[numerical_features].copy()
# Standardize the numerical features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
# Instantiate DBSCAN. Using parameters that resulted in multiple clusters in previous runs.
dbscan = DBSCAN(eps=0.5, min_samples=5)
# Fit the model and get cluster labels
dbscan_labels = dbscan.fit_predict(X_scaled)
# Add cluster labels to the original DataFrame
flattened_df['dbscan_cluster'] = dbscan_labels
def map_clusters_to_recommendations(row):
    """
    Maps DBSCAN cluster labels and other metrics to a recommendation string.
    """
    cluster = row['dbscan_cluster']
    profit = row['profit']
    conversions = row['conversions']
    if cluster == -1:
        return "Investigate: Potential Outlier"
    elif cluster == 0:
        if profit > 0 and conversions > 0:
            return "Optimize: High Profit/Conversion Cluster"
        elif profit > 0:
            return "Monitor: Profitable Cluster (Low Conversions)"
        else:
            return "Analyze: Low Profit/Conversion Cluster"
    else:  # For other clusters
        if profit > 0 and conversions > 0:
            return "Investigate: Potentially High Performing Cluster"
        else:
            return "Monitor: Other Cluster"
# Apply the function to create the 'recommendation' column
flattened_df['recommendation'] = flattened_df.apply(map_clusters_to_recommendations, axis=1)
# 1. Print the value counts of the 'recommendation' column
print("Distribution of Recommendations:")
print(flattened_df['recommendation'].value_counts())
# 2. For each unique value in the 'recommendation' column, filter and analyze
unique_recommendations = flattened_df['recommendation'].unique()
for recommendation in unique_recommendations:
    print(f"\nAnalyzing Recommendation: {recommendation}")
    recommendation_df = flattened_df[flattened_df['recommendation'] == recommendation]
    # 3. Descriptive statistics
    print("Descriptive Statistics for Key Numerical Columns:")
    key_numerical_cols = [
        'cost', 'revenue', 'profit', 'conversions', 'campaign_unique_clicks',
        'roi_confirmed', 'cr', 'lp_ctr', 'cost_per_click'
    ]
    # display(recommendation_df[key_numerical_cols].describe())
    # # 4. Visualizations
    # plt.figure(figsize=(12, 5))
    # plt.subplot(1, 2, 1)
    # sns.histplot(recommendation_df['profit'], bins=30, kde=True)
    # plt.title(f'Profit Distribution for "{recommendation}"')
    # plt.xlabel('Profit')
    # plt.ylabel('Frequency')
    # plt.subplot(1, 2, 2)
    # sns.histplot(recommendation_df['conversions'], bins=10, kde=True, discrete=True)
    # plt.title(f'Conversions Distribution for "{recommendation}"')
    # plt.xlabel('Conversions')
    # plt.ylabel('Frequency')
    # plt.tight_layout()
    # plt.show()
    # print("-" * 50)
# :white_check_mark: Save the model for inference
model_bundle = {
    'scaler': scaler,
    'dbscan': dbscan,
    'features': numerical_features
}
joblib.dump(model_bundle, "dbscan_model.pkl")
print(":white_check_mark: Model bundle saved to 'dbscan_model.pkl'")

