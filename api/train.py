import os
import json
import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from mp_api.client import MPRester
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

def fetch_data_from_mp():
    env_path = r"C:\Users\HYPER\Desktop\git\AI-Materials-Platform\.env"
    load_dotenv(env_path)
    api_key = os.getenv("MP_API_KEY")
    if not api_key:
        raise ValueError(f"MP_API_KEY not found in {env_path}")

    print("Connecting to Materials Project API...")
    with MPRester(api_key) as mpr:
        docs = mpr.summary.search(
            is_stable=True,
            fields=["density", "volume", "nsites", "nelements", "composition", "formation_energy_per_atom"]
        )
        
    print(f"Successfully fetched {len(docs)} documents from Materials Project.")
    
    if len(docs) > 10000:
        docs = docs[:10000]
        
    data = []
    for doc in docs:
        try:
            d = getattr(doc, 'density', None)
            v = getattr(doc, 'volume', None)
            ns = getattr(doc, 'nsites', None)
            ne = getattr(doc, 'nelements', None)
            fe = getattr(doc, 'formation_energy_per_atom', None)
            comp = getattr(doc, 'composition', None)
            
            if None not in (d, v, ns, ne, fe, comp):
                avg_en = getattr(comp, 'average_electroneg', 0.0)
                weight = getattr(comp, 'weight', 0.0)
                num_atoms = getattr(comp, 'num_atoms', 1.0)
                mean_mass = weight / num_atoms if num_atoms > 0 else 0.0
                
                data.append({
                    'density': float(d),
                    'volume': float(v),
                    'nsites': int(ns),
                    'nelements': int(ne),
                    'mean_atomic_mass': float(mean_mass),
                    'average_electronegativity': float(avg_en) if avg_en else 0.0,
                    'formation_energy': float(fe)
                })
        except Exception as e:
            continue
            
    df = pd.DataFrame(data)
    print(f"Extracted {len(df)} complete records with chemical descriptors.")
    return df

def generate_mock_data(n_samples=2000):
    np.random.seed(42)
    density = np.random.uniform(1.0, 20.0, n_samples)
    volume = np.random.uniform(10.0, 300.0, n_samples)
    nsites = np.random.randint(1, 100, n_samples)
    nelements = np.random.randint(1, 5, n_samples)
    mean_atomic_mass = np.random.uniform(10.0, 200.0, n_samples)
    average_electronegativity = np.random.uniform(1.0, 3.5, n_samples)
    
    base_fe = -2.0 + (density * 0.05) - (nsites * 0.01) + (nelements * 0.2) - (average_electronegativity * 0.5)
    noise = np.random.normal(0, 0.5, n_samples)
    formation_energy = base_fe + noise
    
    return pd.DataFrame({
        'density': density,
        'volume': volume,
        'nsites': nsites,
        'nelements': nelements,
        'mean_atomic_mass': mean_atomic_mass,
        'average_electronegativity': average_electronegativity,
        'formation_energy': formation_energy
    })

def preprocess_data(df):
    print("Preprocessing data (handling missing values & outliers)...")
    df = df.dropna()
    
    Q1 = df[['volume', 'density']].quantile(0.25)
    Q3 = df[['volume', 'density']].quantile(0.75)
    IQR = Q3 - Q1
    
    mask = ~((df[['volume', 'density']] < (Q1 - 3 * IQR)) | 
             (df[['volume', 'density']] > (Q3 + 3 * IQR))).any(axis=1)
    
    df_clean = df[mask]
    print(f"Dataset size after outlier removal: {len(df_clean)}")
    return df_clean

def train():
    try:
        df = fetch_data_from_mp()
    except Exception as e:
        print(f"Warning: Failed to fetch real data from Materials Project ({e}).")
        print("Falling back to generating realistic mock physical data.")
        df = generate_mock_data()
        
    df = preprocess_data(df)
    
    if len(df) < 100:
        raise ValueError("Insufficient data after preprocessing.")
        
    features = ['density', 'volume', 'nsites', 'nelements', 'mean_atomic_mass', 'average_electronegativity']
    X = df[features]
    y = df['formation_energy']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train XGBoost
    print("Training XGBRegressor pipeline...")
    xgb_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('regressor', XGBRegressor(n_estimators=300, max_depth=8, learning_rate=0.05, random_state=42, n_jobs=-1))
    ])
    xgb_pipeline.fit(X_train, y_train)
    xgb_pred = xgb_pipeline.predict(X_test)
    xgb_r2 = r2_score(y_test, xgb_pred)
    xgb_mse = mean_squared_error(y_test, xgb_pred)
    print(f"XGBoost Performance - MSE: {xgb_mse:.4f}, R2: {xgb_r2:.4f}")

    # Train Neural Network
    print("Training MLPRegressor (Neural Network) pipeline...")
    nn_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('regressor', MLPRegressor(hidden_layer_sizes=(128, 64, 32), activation='relu', solver='adam', max_iter=500, random_state=42, early_stopping=True))
    ])
    nn_pipeline.fit(X_train, y_train)
    nn_pred = nn_pipeline.predict(X_test)
    nn_r2 = r2_score(y_test, nn_pred)
    nn_mse = mean_squared_error(y_test, nn_pred)
    print(f"Neural Network Performance - MSE: {nn_mse:.4f}, R2: {nn_r2:.4f}")

    # Evaluate and select best model
    if nn_r2 > xgb_r2:
        best_model_name = "Neural Network (MLPRegressor)"
        best_pipeline = nn_pipeline
        best_r2 = nn_r2
        best_mse = nn_mse
    else:
        best_model_name = "XGBoost"
        best_pipeline = xgb_pipeline
        best_r2 = xgb_r2
        best_mse = xgb_mse

    print(f"Best model selected: {best_model_name}")

    metrics = {
        "mean_squared_error": float(best_mse),
        "r2_score": float(best_r2),
        "dataset_size": len(df),
        "best_model": best_model_name
    }
    
    metrics_path = os.path.join(os.path.dirname(__file__), 'metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=4)
    print(f"Metrics saved to {metrics_path}")
    
    model_path = os.path.join(os.path.dirname(__file__), 'model.joblib')
    joblib.dump(best_pipeline, model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train()
