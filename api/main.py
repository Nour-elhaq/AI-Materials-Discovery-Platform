from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse
from pydantic import BaseModel, Field
import asyncio
import os
import tempfile
import shutil
from starlette.background import BackgroundTask
from model import predictor
from lammps_generator import generate_lammps_script, extract_ff_parameters

app = FastAPI(
    title="Formation Energy Prediction API",
    description="A production-ready FastAPI backend for predicting material formation energy using the best performing machine learning pipeline (XGBoost or Neural Network) trained on authentic Materials Project data.",
    version="3.0.0"
)

# Define the input data schema reflecting deeper chemical features
class MaterialFeatures(BaseModel):
    density: float = Field(..., ge=0.0, description="Material density in g/cm³")
    volume: float = Field(..., ge=0.0, description="Volume of the unit cell in Å³")
    nsites: int = Field(..., ge=1, description="Number of sites (atoms) in the unit cell")
    nelements: int = Field(..., ge=1, description="Number of unique elements")
    mean_atomic_mass: float = Field(..., ge=0.0, description="Mean atomic mass of the composition")
    average_electronegativity: float = Field(..., ge=0.0, description="Average electronegativity of the composition")
    elements: list[str] = Field(default=[], description="List of element symbols")

class PairCoeff(BaseModel):
    atom_pair: str
    epsilon: float
    sigma: float

# Define the output data schema
class PredictionResponse(BaseModel):
    predicted_formation_energy_ev_per_atom: float
    force_field: str
    pair_coeffs: list[PairCoeff]

@app.get("/")
def read_root():
    return {"message": "Welcome to the Formation Energy Prediction API. Use the POST /predict endpoint to get predictions."}

@app.post("/predict", response_model=PredictionResponse)
def predict_formation_energy(features: MaterialFeatures):
    # Convert the pydantic model to a list of features in the correct order
    feature_list = [
        features.density,
        features.volume,
        features.nsites,
        features.nelements,
        features.mean_atomic_mass,
        features.average_electronegativity
    ]
    
    # Get the prediction from the scikit-learn model
    prediction = predictor.predict(feature_list)
    
    # Extract FF parameters
    ff_data = extract_ff_parameters(features)
    
    return PredictionResponse(
        predicted_formation_energy_ev_per_atom=prediction,
        force_field=ff_data["force_field"],
        pair_coeffs=ff_data["pair_coeffs"]
    )

@app.post("/generate-lammps", response_class=PlainTextResponse)
def generate_lammps(features: MaterialFeatures):
    """
    Generate a LAMMPS simulation script dynamically tailored 
    to the specific material features.
    """
    script_content = generate_lammps_script(features)
    return script_content

class TrajectoryResponse(BaseModel):
    trajectory: str
    message: str

@app.post("/simulate-trajectory")
async def simulate_trajectory(features: MaterialFeatures):
    """
    Dynamically generates a LAMMPS script, executes it via subprocess,
    and returns the resulting trajectory.
    """
    script_content = generate_lammps_script(features)
    
    tmpdir = tempfile.mkdtemp()
    input_script_path = os.path.join(tmpdir, "run.in")
    dump_file_path = os.path.join(tmpdir, "dump.lammpstrj")
    
    with open(input_script_path, "w") as f:
        f.write(script_content)
        
    lmp_exe = os.getenv('LMP_EXE', r"C:\Users\HYPER\AppData\Local\LAMMPS 64-bit 10Dec2025-MSMPI\bin\lmp.exe")
    
    process = await asyncio.create_subprocess_exec(
        lmp_exe, "-in", input_script_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=tmpdir
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45.0)
    except asyncio.TimeoutError:
        process.kill()
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(status_code=408, detail="LAMMPS simulation timed out")
        
    if process.returncode != 0:
        error_msg = stderr.decode() if stderr else stdout.decode()
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"LAMMPS error: {error_msg}")
        
    if not os.path.exists(dump_file_path):
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Trajectory file was not generated.")
        
    return FileResponse(dump_file_path, background=BackgroundTask(shutil.rmtree, tmpdir))
