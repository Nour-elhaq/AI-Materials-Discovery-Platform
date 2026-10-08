import math

# Universal Force Field (UFF) parameters for common elements
# Format: { "Symbol": {"mass": mass_in_amu, "eps": epsilon_in_eV, "sig": sigma_in_Angstroms} }
UFF_DICT = {
    "H": {"mass": 1.008, "eps": 0.0019, "sig": 2.57},
    "He": {"mass": 4.003, "eps": 0.0009, "sig": 2.10},
    "Li": {"mass": 6.941, "eps": 0.0011, "sig": 2.45},
    "Be": {"mass": 9.012, "eps": 0.0037, "sig": 2.45},
    "B": {"mass": 10.811, "eps": 0.0039, "sig": 3.58},
    "C": {"mass": 12.011, "eps": 0.0045, "sig": 3.43},
    "N": {"mass": 14.007, "eps": 0.0030, "sig": 3.26},
    "O": {"mass": 15.999, "eps": 0.0026, "sig": 3.12},
    "F": {"mass": 18.998, "eps": 0.0022, "sig": 3.36},
    "Ne": {"mass": 20.180, "eps": 0.0018, "sig": 2.89},
    "Na": {"mass": 22.990, "eps": 0.0013, "sig": 2.98},
    "Mg": {"mass": 24.305, "eps": 0.0048, "sig": 2.69},
    "Al": {"mass": 26.982, "eps": 0.022, "sig": 4.01},
    "Si": {"mass": 28.085, "eps": 0.017, "sig": 3.83},
    "P": {"mass": 30.974, "eps": 0.013, "sig": 3.70},
    "S": {"mass": 32.065, "eps": 0.012, "sig": 3.59},
    "Cl": {"mass": 35.45, "eps": 0.0099, "sig": 3.52},
    "Ar": {"mass": 39.948, "eps": 0.0081, "sig": 3.40},
    "K": {"mass": 39.098, "eps": 0.0015, "sig": 3.40},
    "Ca": {"mass": 40.078, "eps": 0.010, "sig": 3.03},
    "Sc": {"mass": 44.956, "eps": 0.0008, "sig": 2.94},
    "Ti": {"mass": 47.867, "eps": 0.0007, "sig": 2.83},
    "V": {"mass": 50.942, "eps": 0.0007, "sig": 2.80},
    "Cr": {"mass": 51.996, "eps": 0.0006, "sig": 2.69},
    "Mn": {"mass": 54.938, "eps": 0.0006, "sig": 2.64},
    "Fe": {"mass": 55.845, "eps": 0.00057, "sig": 2.59},
    "Co": {"mass": 58.933, "eps": 0.0006, "sig": 2.56},
    "Ni": {"mass": 58.693, "eps": 0.0006, "sig": 2.52},
    "Cu": {"mass": 63.546, "eps": 0.00022, "sig": 3.11},
    "Zn": {"mass": 65.38, "eps": 0.0054, "sig": 2.46},
    "Ga": {"mass": 69.723, "eps": 0.018, "sig": 3.91},
    "Ge": {"mass": 72.630, "eps": 0.015, "sig": 3.81},
    "As": {"mass": 74.922, "eps": 0.014, "sig": 3.78},
    "Se": {"mass": 78.971, "eps": 0.013, "sig": 3.76},
    "Br": {"mass": 79.904, "eps": 0.011, "sig": 3.73},
    "Kr": {"mass": 83.798, "eps": 0.010, "sig": 3.69},
    "I": {"mass": 126.90, "eps": 0.017, "sig": 4.01},
}

def generate_lammps_script(features) -> str:
    # Estimate simulation box dimensions based on volume
    L = features.volume ** (1.0 / 3.0)
    if L < 1.0:
        L = 10.0
        
    elements = getattr(features, "elements", [])
    if not elements:
        # Fallback if elements not provided
        n_types = features.nelements
        element_data = [{"mass": features.mean_atomic_mass, "eps": max(0.1 * features.average_electronegativity, 0.1), "sig": max(1.0, (features.volume / max(1, features.nsites)) ** (1.0 / 3.0) * 0.8)}] * n_types
    else:
        n_types = len(elements)
        element_data = []
        for el in elements:
            if el in UFF_DICT:
                element_data.append(UFF_DICT[el])
            else:
                # Fallback for unknown element
                element_data.append({"mass": features.mean_atomic_mass, "eps": 0.01, "sig": 3.0})

    script = f"""# PRODUCTION-GRADE LAMMPS Input Script Generated from Material Features
# Density: {features.density} g/cm^3
# Volume: {features.volume} A^3
# N-sites: {features.nsites}
# N-elements: {features.nelements}
"""
    if elements:
        script += f"# Elements: {', '.join(elements)}\n"
        
    script += f"""# Mean Atomic Mass: {features.mean_atomic_mass}
# Avg Electronegativity: {features.average_electronegativity}

units           metal
dimension       3
boundary        p p p
atom_style      charge

# Box Definition
region          sim_box block 0 {L:.4f} 0 {L:.4f} 0 {L:.4f} units box
create_box      {n_types} sim_box
"""
    
    # Distribute atoms
    n_total = features.nsites
    
    base_count = n_total // n_types
    remainder = n_total % n_types
    
    for i in range(1, n_types + 1):
        count = base_count + (1 if i <= remainder else 0)
        seed = 12345 + i * 10
        if count > 0:
            script += f"create_atoms    {i} random {count} {seed} sim_box\n"
        mass = element_data[i-1]["mass"]
        script += f"mass            {i} {mass:.4f}\n"

    script += """
# ----------------------------------------------------
# 1. Initialization and Thermodynamics Setup
# ----------------------------------------------------
timestep        0.001
thermo          100
thermo_style    custom step temp pe ke etotal press vol lx ly lz density

# Output configuration for trajectory (using unwrapped coordinates)
dump            ovito_dump all custom 100 dump.lammpstrj id type xu yu zu
dump_modify     ovito_dump sort id

# ----------------------------------------------------
# 2. Resolve initial overlaps using soft potential
# ----------------------------------------------------
neighbor        2.0 bin
neigh_modify    delay 10 every 1 check yes

pair_style      soft 2.0
"""
    for i in range(1, n_types + 1):
        for j in range(i, n_types + 1):
            script += f"pair_coeff      {i} {j} 10.0\n"
            
    script += """
variable        prefactor equal ramp(0,100)
fix             1 all adapt 1 pair soft a * * v_prefactor
fix             2 all nve/limit 0.1
run             1000
unfix           2
unfix           1

# Initial minimization after soft push-off
minimize        1e-4 1e-6 100 1000

# ----------------------------------------------------
# 3. Main Simulation Potential
# ----------------------------------------------------
# Fallback Generic Lennard-Jones potential
pair_style      lj/cut 8.0
pair_modify     mix arithmetic
"""
    # Define diagonal elements only, let LAMMPS mix
    for i in range(1, n_types + 1):
        eps_i = element_data[i-1]["eps"]
        sig_i = element_data[i-1]["sig"]
        script += f"pair_coeff      {i} {i} {eps_i:.6f} {sig_i:.6f}\n"

    script += """
# ----------------------------------------------------
# 4. Box Relaxation & Cohesive Energy at 0K
# ----------------------------------------------------
min_style       cg
minimize        1.0e-4 1.0e-6 10000 10000

variable        natoms equal count(all)
variable        cohesive_energy_0K equal pe/v_natoms
print           "=================================================="
print           "Cohesive Energy (0K): ${cohesive_energy_0K} eV/atom"
print           "=================================================="

# ----------------------------------------------------
# 5. Equilibration & Production
# ----------------------------------------------------
"""
    if n_total == 1:
        script += """
# Single atom system: temperature rescaling is invalid.
# Assigning fixed velocity and running NVE.
velocity        all set 0.01 0.01 0.01
fix             prod_nve all nve
run             10000
unfix           prod_nve
"""
    else:
        script += """
velocity        all create 300.0 87287 dist gaussian mom no rot no

# Phase 1: NVT Heating
fix             eq_nvt all nvt temp 10.0 300.0 0.1
run             5000
unfix           eq_nvt

# Phase 2: NPT Box Relaxation
fix             eq_npt all npt temp 300.0 300.0 0.1 iso 0.0 0.0 1.0
run             10000
unfix           eq_npt

# ----------------------------------------------------
# 6. NVT Production
# ----------------------------------------------------
fix             prod_nvt all nvt temp 300.0 300.0 0.1
run             10000
unfix           prod_nvt
"""
    return script

def extract_ff_parameters(features) -> dict:
    elements = getattr(features, "elements", [])
    if not elements:
        n_types = features.nelements
        elements_labels = [f"Type_{i+1}" for i in range(n_types)]
        element_data = [{"mass": features.mean_atomic_mass, "eps": max(0.1 * features.average_electronegativity, 0.1), "sig": max(1.0, (features.volume / max(1, features.nsites)) ** (1.0 / 3.0) * 0.8)}] * n_types
    else:
        n_types = len(elements)
        elements_labels = elements
        element_data = []
        for el in elements:
            if el in UFF_DICT:
                element_data.append(UFF_DICT[el])
            else:
                element_data.append({"mass": features.mean_atomic_mass, "eps": 0.01, "sig": 3.0})
                
    pair_coeffs = []
    # Lorentz-Berthelot mixing rules: arithmetic for sigma, geometric for epsilon
    for i in range(n_types):
        for j in range(i, n_types):
            eps_i = element_data[i]["eps"]
            sig_i = element_data[i]["sig"]
            eps_j = element_data[j]["eps"]
            sig_j = element_data[j]["sig"]
            
            eps_mix = math.sqrt(eps_i * eps_j)
            sig_mix = (sig_i + sig_j) / 2.0
            
            pair_coeffs.append({
                "atom_pair": f"{elements_labels[i]}-{elements_labels[j]}",
                "epsilon": eps_mix,
                "sigma": sig_mix
            })
            
    return {
        "force_field": "UFF (Lennard-Jones) with Lorentz-Berthelot mixing",
        "pair_coeffs": pair_coeffs
    }
