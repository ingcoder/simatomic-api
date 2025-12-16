"""
SimAtomic Client - Test Script
Test script for submitting and monitoring molecular dynamics jobs
"""

import time
from simatomic_client import SimAtomicClient

# ============================================================================
# Configuration Parameters
# ============================================================================

# MM-PBSA Analysis Parameters
# Used for calculating binding free energies in protein-protein interactions
mmpbsa_parameters = {
    "mode": "mmpbsa",
    
    # Trajectory processing
    "mmpbsa_stride": 100,           # Stride when converting trajectory to NetCDF
    "mmpbsa_startframe": 0,         # First frame to analyze
    "mmpbsa_endframe": 1000,        # Last frame to analyze
    "mmpbsa_interval": 100,         # Interval between analyzed frames
    
    # MM-PBSA settings
    "igb": 5,                       # Generalized Born model (5 or 8 common for PPIs)
    
    # Decomposition analysis (per-residue contribution)
    "use_decomp": False,            # Set True for per-residue energy breakdown
    "decomp_idecomp": 3,            # Decomposition scheme (if use_decomp=True)
    
    # Masking/stripping parameters
    "strip_mask_input": ":HOH:NA:CL",                # Mask used in mmpbsa.in
    "strip_mask_items": [":HOH", ":NA", ":CL"],      # Mask used for ante-MMPBSA -s
    "ligand_chain_mask": ":100-110",                 # Ligand residue range
}

# Ensemble Analysis Parameters (Alternative mode)
# Uncomment to use ensemble analysis instead of MM-PBSA
analysis_parameters = {
    "mode": "analysis",
    "start_frame": 0,
    "atom_selection": "name CA",                    # Atom selection for analysis
    "tica_lag_time": 30,                            # TICA lag time
    "tica_dimensions": 5,                           # Number of TICA components
    "min_cluster_size": 10,                         # Minimum cluster size for HDBSCAN
    "min_samples": 10,                              # Minimum samples for HDBSCAN
    "autocorr_maxtime": None,                       # Max time for autocorrelation
    "autocorr_threshold": 0.0,                      # Autocorrelation threshold
    "autocorr_component": 4,                        # Component for autocorrelation
    "ensemble_output_path": "ensemble_analysis_dashboard.html",
    "rmsd_output_path": "protein_ligand_rmsd_plots.html",
}

# ============================================================================
# Input Files
# ============================================================================

analysis_input_path = "path/to/analysis_input.zip"
mmpbsa_input_path = "path/to/mmpbsa_input.zip"

# ============================================================================
# Initialize Client & Submit Job
# ============================================================================

# Initialize SimAtomic client with API key
# Available modes: "mmpbsa", "analysis", "batch_simulation"
client = SimAtomicClient(api_key="1234567890")

# Submit the job
print("Submitting job to SimAtomic...")
# job_id = client.run_job(mmpbsa_input_path, mmpbsa_parameters)
job_id = client.run_job(analysis_input_path, analysis_parameters)
print(f"Job submitted with ID: {job_id}\n")

# ============================================================================
# Poll for Results
# ============================================================================

MAX_POLLS = 100
POLL_INTERVAL = 30  # seconds

for i in range(MAX_POLLS):
    print(f"[Poll {i+1}/{MAX_POLLS}] Checking job status...")
    
    results = client.poll_job(job_id)
    status = results['job_status']
    
    if status == "success":
        print(f"✅ Job {job_id} completed successfully!")
        print(f"Results: {results['message']}")
        break
        
    elif status == "failed":
        print(f"❌ Job {job_id} failed")
        print(f"Error: {results.get('message', 'No error message provided')}")
        break
        
    else:
        # Job is still processing
        if status == "queued":
            print(f"⏳ Job {job_id} is queued, waiting to start...")
        else:
            print(f"🔄 Job {job_id} is running...")
        
        time.sleep(POLL_INTERVAL)
