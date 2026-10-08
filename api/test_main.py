import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from main import app
from model import FormationEnergyPredictor
import numpy as np
import os

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "Welcome" in response.json()["message"]

def test_predict_valid_input():
    payload = {
        "density": 7.8,
        "volume": 55.85,
        "nsites": 2,
        "nelements": 2,
        "mean_atomic_mass": 12.0,
        "average_electronegativity": 2.5
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "predicted_formation_energy_ev_per_atom" in data
    assert isinstance(data["predicted_formation_energy_ev_per_atom"], float)

def test_predict_missing_field():
    payload = {
        "density": 7.8,
        "volume": 55.85,
        "nsites": 2,
        "mean_atomic_mass": 12.0
        # missing nelements and average_electronegativity
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()

def test_predict_invalid_type():
    payload = {
        "density": "invalid_string",
        "volume": 55.85,
        "nsites": 2,
        "nelements": 2,
        "mean_atomic_mass": 12.0,
        "average_electronegativity": 2.5
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()

def test_predict_negative_density():
    payload = {
        "density": -1.0,
        "volume": 55.85,
        "nsites": 2,
        "nelements": 2,
        "mean_atomic_mass": 12.0,
        "average_electronegativity": 2.5
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(err["loc"] == ["body", "density"] and err["type"] == "greater_than_equal" for err in details)

def test_predict_negative_volume():
    payload = {
        "density": 7.8,
        "volume": -5.0,
        "nsites": 2,
        "nelements": 2,
        "mean_atomic_mass": 12.0,
        "average_electronegativity": 2.5
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(err["loc"] == ["body", "volume"] and err["type"] == "greater_than_equal" for err in details)

def test_predict_invalid_nsites():
    payload = {
        "density": 7.8,
        "volume": 55.85,
        "nsites": 0,
        "nelements": 2,
        "mean_atomic_mass": 12.0,
        "average_electronegativity": 2.5
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(err["loc"] == ["body", "nsites"] and err["type"] == "greater_than_equal" for err in details)

def test_clamping_behavior():
    """
    Test that the model allows negative predictions since formation energy can be negative.
    """
    predictor = FormationEnergyPredictor()
    
    mock_pipeline = MagicMock()
    mock_pipeline.predict.return_value = np.array([-1.5])
    
    predictor.pipeline = mock_pipeline
    
    features = [7.8, 55.85, 2, 2, 12.0, 2.5]
    prediction = predictor.predict(features)
    
    assert prediction == -1.5
    mock_pipeline.predict.assert_called_once()

def test_model_predictor_invalid_shape():
    predictor = FormationEnergyPredictor()
    predictor.load_model()
    # Missing features
    features = [7.8, 55.85, 2] 
    
    with pytest.raises(ValueError):
        predictor.predict(features)

def test_model_predictor_file_not_found():
    predictor = FormationEnergyPredictor()
    predictor.model_path = "non_existent_model.joblib"
    predictor.pipeline = None
    
    with pytest.raises(FileNotFoundError):
        predictor.load_model()


def test_generate_lammps_valid_input():
    payload = {
        "density": 7.8,
        "volume": 55.85,
        "nsites": 4,
        "nelements": 2,
        "mean_atomic_mass": 55.8,
        "average_electronegativity": 1.8
    }
    response = client.post("/generate-lammps", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    
    script = response.text
    # Verify key LAMMPS directives are present
    assert "units           metal" in script
    assert "dimension       3" in script
    assert "pair_style      soft 2.0" in script
    assert "pair_style      lj/cut 8.0" in script
    assert "create_atoms" in script
    assert "mass" in script
    assert "minimize" in script
    assert "run             1000" in script

def test_generate_lammps_invalid_input():
    # Test with invalid nsites (should be >= 1)
    payload = {
        "density": 7.8,
        "volume": 55.85,
        "nsites": 0,
        "nelements": 2,
        "mean_atomic_mass": 55.8,
        "average_electronegativity": 1.8
    }
    response = client.post("/generate-lammps", json=payload)
    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(err["loc"] == ["body", "nsites"] and err["type"] == "greater_than_equal" for err in details)

def test_generate_lammps_negative_volume():
    # Test with negative volume
    payload = {
        "density": 7.8,
        "volume": -10.0,
        "nsites": 4,
        "nelements": 2,
        "mean_atomic_mass": 55.8,
        "average_electronegativity": 1.8
    }
    response = client.post("/generate-lammps", json=payload)
    assert response.status_code == 422
