# SimAtomic API Client

A Python client for running molecular dynamics analysis and energy calculations (MM/PBSA) jobs remotely on the SimAtomic cloud platform.

---

## 1. Installation

### Requirements

- Python 3.6+
- `requests` library (automatically installed with the package)

### Install from ZIP

Download the `simatomic-client.zip` package and install it with pip:

```bash
pip install simatomic-client.zip
```

### Install for Development (Editable Mode)

If you want to modify the source code and have changes reflected immediately:

```bash
# From the directory containing the zippped or unzipped simatomic-client folder
pip install -e simatomic-client/
or
pip install -e simatomic-client.zip
```

### Verify Installation

After installation, verify it works:

```python
from simatomic_client import SimAtomicClient
print("SimAtomic client installed successfully!")
```

---

## 2. Quick Start

This example shows the basic workflow. For job configuration details, see **Section 4** (Job Modes) and **Section 5** (Configuration Parameters).

```python
from simatomic_client import SimAtomicClient
import time

# Initialize client with your API key
client = SimAtomicClient(api_key="your-api-key")

# Define job configuration (see Section 4 for mode options)
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
    "ligand_chain_mask": ":121-134",                 # Ligand residue range
}


# Run the job (see Section 8 for method details)
job_id = client.run_job("/path/to/trajectory.zip", mmpbsa_parameters)

# Poll for results (see Section 7 for status codes)
while True:
    result = client.poll_job(job_id)

    if result['job_status'] == "success":
        print("Job completed!")
        break
    elif result['job_status'] == "failed":
        print("Job failed")
        break
    else:
        time.sleep(30)

```

---

## 3. Input File Structure

Both job modes require a `.zip` file as input. The required contents depend on the mode.

### 3.1 MM-PBSA Input

For `mode: "mmpbsa"` jobs, your `.zip` must contain:

| File                      | Description                  |
| ------------------------- | ---------------------------- |
| `final_md_trajectory.xtc` | Trajectory file              |
| `emin.pdb`                | Energy minimized structure   |
| `openff_topology.pdb`     | OpenForceField topology file |

### 3.2 Ensemble Analysis Input

For `mode: "analysis"` jobs, your `.zip` must contain:

| File                      | Description                |
| ------------------------- | -------------------------- |
| `final_md_trajectory.xtc` | Trajectory file            |
| `emin.pdb`                | Energy minimized structure |
| `simulation_config.yaml`  | Simulation configuration   |

---

## 4. Job Modes

SimAtomic supports two job modes. Choose the appropriate mode based on your analysis needs and configure it using the parameters in **Section 5**.

### 4.1 Trajectory Analysis

**Purpose:** Analyze trajectories from UnoMD to identify conformational clusters and screen structural dynamics.

Use `mode: "analysis"` for ensemble clustering and TICA decomposition. This mode is ideal for:

- **Identifying representative conformations** that occur during simulation
- **Generating training datasets** from cluster-derived PDB structures
- **Quick screening** of structural dynamics, stability, and protein-protein binding
- **Flagging candidates** for downstream MM-PBSA calculations

**Output:**

1. **Cluster Dashboard** - Interactive visualization of conformational clusters with representative structures
2. **Dynamics Dashboard** - RMSD/RMSF plots for rapid screening of stability and binding dynamics
3. **Cluster PDB files** - Representative structures for dataset augmentation

```python
config = {
    "mode": "analysis",
    "start_frame": 0,
    "atom_selection": "name CA",
    "tica_lag_time": 30,
    "tica_dimensions": 5,
    "min_cluster_size": 10,
    "min_samples": 10
}
```

See **Section 5.1** for all available parameters.

### 4.2 MM-PBSA Calculation

**Purpose:** Calculate relative binding free energies for protein-protein interactions to rank and prioritize candidates.

Use `mode: "mmpbsa"` for binding free energy calculations. This mode is ideal for:

- **Ranking candidate molecules** based on binding affinity
- **Quantifying protein-protein interactions** with energy values
- **Follow-up analysis** on promising candidates identified from trajectory screening

**Note:** MM-PBSA calculations are computationally expensive. Use trajectory analysis mode (Section 4.1) first to screen and identify high-priority candidates.

**Output:**

- `FINAL_RESULTS_MMPBSA.dat` containing binding free energy values for ranking

```python
config = {
    "mode": "mmpbsa",
    "mmpbsa_stride": 100,
    "mmpbsa_startframe": 0,
    "mmpbsa_endframe": 1000,
    "mmpbsa_interval": 100,
    "igb": 5,
    "use_decomp": False,
    "strip_mask_input": ":HOH:NA:CL",
    "strip_mask_items": [":HOH", ":NA", ":CL"],
    "ligand_chain_mask": ":100-110"
}
```

See **Section 5.2** for all available parameters.

---

## 5. Configuration Parameters

### 5.1 Trajectory Analysis Parameters

These parameters apply when `mode` is set to `"analysis"` (see **Section 4.1**).

| Parameter            | Type  | Default     | Description                             |
| -------------------- | ----- | ----------- | --------------------------------------- |
| `mode`               | str   | —           | Must be `"analysis"`                    |
| `start_frame`        | int   | `0`         | First frame to analyze                  |
| `atom_selection`     | str   | `"name CA"` | MDAnalysis atom selection string        |
| `tica_lag_time`      | int   | `30`        | Lag time for TICA decomposition         |
| `tica_dimensions`    | int   | `5`         | Number of TICA dimensions to retain     |
| `min_cluster_size`   | int   | `10`        | Minimum cluster size for HDBSCAN        |
| `min_samples`        | int   | `10`        | HDBSCAN min_samples parameter           |
| `autocorr_maxtime`   | int   | `None`      | Max time for autocorrelation (optional) |
| `autocorr_threshold` | float | `0.0`       | Autocorrelation threshold               |
| `autocorr_component` | int   | `4`         | Component for autocorrelation analysis  |

### 5.2 MM-PBSA Parameters

These parameters apply when `mode` is set to `"mmpbsa"` (see **Section 4.2**).

| Parameter           | Type | Default                  | Description                                       |
| ------------------- | ---- | ------------------------ | ------------------------------------------------- |
| `mode`              | str  | —                        | Must be `"mmpbsa"`                                |
| `mmpbsa_stride`     | int  | `100`                    | Stride when converting trajectory to NetCDF       |
| `mmpbsa_startframe` | int  | `0`                      | First frame for MM-PBSA                           |
| `mmpbsa_endframe`   | int  | `1000`                   | Last frame for MM-PBSA                            |
| `mmpbsa_interval`   | int  | `100`                    | Frame interval for analysis                       |
| `igb`               | int  | `5`                      | Generalized Born model (5 or 8 for PPIs)          |
| `use_decomp`        | bool | `False`                  | Enable per-residue decomposition                  |
| `decomp_idecomp`    | int  | `3`                      | Decomposition scheme (when `use_decomp=True`)     |
| `strip_mask_input`  | str  | `":HOH:NA:CL"`           | Mask for stripping in mmpbsa.in                   |
| `strip_mask_items`  | list | `[":HOH", ":NA", ":CL"]` | Masks for ante-MMPBSA stripping                   |
| `ligand_chain_mask` | str  | —                        | Residue mask for ligand chain (e.g. `":121-134"`) |

---

## 6. Job Status

After submitting a job (see **Section 8**), poll for status using `poll_job()`. The following status codes are returned:

| Status    | Description                     |
| --------- | ------------------------------- |
| `queued`  | Job submitted, waiting to start |
| `running` | Job is processing               |
| `success` | Job completed successfully      |
| `failed`  | Job failed                      |

---

## 7. Results and Output

When a job completes successfully (status: `success`), the response includes a download link containing the analysis results.

### 7.1 MM-PBSA Results

For `mode: "mmpbsa"` jobs, the downloaded results folder contains:

| File                       | Description                                      |
| -------------------------- | ------------------------------------------------ |
| `FINAL_RESULTS_MMPBSA.dat` | Energy data and binding free energy calculations |
| Additional output files    | Supporting MM-PBSA calculation files             |

**Key output file:** `FINAL_RESULTS_MMPBSA.dat` contains the final energy values.

### 7.2 Ensemble Analysis Results

For `mode: "analysis"` jobs, the downloaded results folder contains:

| Output                     | Description                                       |
| -------------------------- | ------------------------------------------------- |
| Analysis dashboard (HTML)  | Interactive dashboard with clustered trajectories |
| RMSD/RMSF dashboard (HTML) | Quick screening dashboard with RMSD and RMSF data |
| Cluster PDB files          | PDB structures from cluster analysis              |

**Example polling with download link:**

```python
result = client.poll_job(job_id)

if result['job_status'] == "success":
    print("Job completed successfully!")
    download_url = result['message']  # Contains the download link
    print(f"Download results at: {download_url}")
```

---

## 8. API Methods

The `SimAtomicClient` class provides these methods:

| Method                       | Description                                               |
| ---------------------------- | --------------------------------------------------------- |
| `run_job(file_path, config)` | Upload file and start job. Returns `job_id`               |
| `poll_job(job_id)`           | Check job status. Returns `{job_id, job_status, message}` |

**Usage:**

```python
# Initialize (Section 2)
client = SimAtomicClient(api_key="your-api-key")

# Submit job with config (Section 4-5) and input file (Section 3)
job_id = client.run_job("/path/to/input.zip", config)

# Poll until complete (Section 6)
result = client.poll_job(job_id)
```

# simatomic_api

SimAtomic Official API for Scalable Molecular Dynamics, MM/PBSA Free-Energy Computation, and Advanced Simulation Analytics in the Cloud
