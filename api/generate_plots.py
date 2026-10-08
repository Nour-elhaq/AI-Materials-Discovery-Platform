import os
import joblib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from train import fetch_data_from_mp, generate_mock_data, preprocess_data

# Set up styling for the plots
sns.set_theme(style="whitegrid")

def main():
    base_dir = os.path.dirname(__file__)
    plots_dir = os.path.join(base_dir, 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    model_path = os.path.join(base_dir, 'model.joblib')
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found at {model_path}. Please run train.py first.")
    
    print("Loading model from disk...")
    pipeline = joblib.load(model_path)
    
    print("Retrieving dataset for plotting...")
    try:
        df = fetch_data_from_mp()
    except Exception as e:
        print("API Key not found or fetch failed. Falling back to robust mock data for plotting.")
        df = generate_mock_data()
        
    df = preprocess_data(df)
    
    # Define features and targets explicitly including new descriptors
    features = ['density', 'volume', 'nsites', 'nelements', 'mean_atomic_mass', 'average_electronegativity']
    X = df[features]
    y_actual = df['formation_energy']
    
    print("Generating predictions on the dataset...")
    y_pred = pipeline.predict(X)
    residuals = y_actual - y_pred
    
    # 1. Actual vs Predicted
    print("Generating Actual vs. Predicted plot...")
    plt.figure(figsize=(8, 6))
    plt.scatter(y_actual, y_pred, alpha=0.5, color='blue', edgecolor='k')
    min_val = min(y_actual.min(), y_pred.min())
    max_val = max(y_actual.max(), y_pred.max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', lw=2, label='Ideal Prediction')
    plt.title('Actual vs Predicted Formation Energy (XGBoost)')
    plt.xlabel('Actual Formation Energy (eV/atom)')
    plt.ylabel('Predicted Formation Energy (eV/atom)')
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'actual_vs_predicted.png'), dpi=300)
    plt.close()
    
    # 2. Residuals Scatter
    print("Generating Residuals Scatter plot...")
    plt.figure(figsize=(8, 6))
    plt.scatter(y_pred, residuals, alpha=0.5, color='orange', edgecolor='k')
    plt.axhline(y=0, color='r', linestyle='--', lw=2)
    plt.title('Residuals vs Predicted Formation Energy (XGBoost)')
    plt.xlabel('Predicted Formation Energy (eV/atom)')
    plt.ylabel('Residuals (Actual - Predicted)')
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'residuals_scatter.png'), dpi=300)
    plt.close()
    
    # 3. Residuals Distribution
    print("Generating Residuals Distribution plot...")
    plt.figure(figsize=(8, 6))
    sns.histplot(residuals, kde=True, color='green')
    plt.title('Distribution of Residuals (XGBoost)')
    plt.xlabel('Residuals (eV/atom)')
    plt.ylabel('Frequency')
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'residuals_distribution.png'), dpi=300)
    plt.close()
    
    # 4. Feature Importance
    print("Generating Feature Importance plot...")
    xgb_model = pipeline.named_steps['regressor']
    importances = xgb_model.feature_importances_
    
    indices = np.argsort(importances)[::-1]
    sorted_features = [features[i] for i in indices]
    sorted_importances = importances[indices]
    
    plt.figure(figsize=(8, 6))
    sns.barplot(x=sorted_importances, y=sorted_features, hue=sorted_features, palette="viridis", legend=False)
    plt.title('Feature Importances (XGBoost)')
    plt.xlabel('Relative Importance')
    plt.ylabel('Feature')
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'feature_importance.png'), dpi=300)
    plt.close()
    
    print(f"All plots successfully saved to: {plots_dir}")

if __name__ == "__main__":
    main()
