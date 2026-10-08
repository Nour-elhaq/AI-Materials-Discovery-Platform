import numpy as np
import joblib
import os

class FormationEnergyPredictor:
    def __init__(self):
        self.model_path = os.path.join(os.path.dirname(__file__), 'model.joblib')
        self.pipeline = None

    def load_model(self):
        if self.pipeline is None:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file not found at {self.model_path}. Please run train.py first.")
            self.pipeline = joblib.load(self.model_path)

    def predict(self, features: list[float]) -> float:
        """
        Predict the formation energy based on input features.
        """
        self.load_model()
        X = np.array([features])
        prediction = self.pipeline.predict(X)
        
        # We do NOT clamp the output since formation energy can be negative (stable materials have negative formation energy)
        return float(prediction[0])

# Instantiate a global predictor for the app to use
predictor = FormationEnergyPredictor()
