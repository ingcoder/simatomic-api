"""
SimAtomic Client - Test Script
Test script for submitting and monitoring molecular dynamics jobs
"""

import time
import os
import logging
from pathlib import Path
from simatomic_client import SimAtomicClient, get_configs, create_input_zip, create_input_analysis_zip
import glob
from simatomic_client import create_input_analysis_zip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("example.log"),
    ],
)
logger = logging.getLogger("simatomic")


# ============================================================================
# Initialize Client & Submit Job
# ============================================================================

def submit_jobs(config_map, mode="simulation", filename=None):
    # Initialize SimAtomic client with API key
    logger.info("Submitting job to SimAtomic...")
    if filename is not None:
        zip_files = [filename]
        job_ids = [client.run_job(path, config_map[mode]) for path in zip_files]
    else:
        try:
            zip_files = glob.glob(f"*{mode}*.zip")
            job_ids = [client.run_job(path, config_map[mode]) for path in zip_files]
        except Exception as e:
            logger.error(f"Error submitting job: {e}")
            return []


    for job_id in job_ids:
        logger.info(f"Job submitted with ID: {job_id}")
    return job_ids

# ============================================================================
# Poll for Results
# ============================================================================

def poll_jobs(job_ids, max_polls=100, poll_interval_seconds=10, output_dir=None):
    pending = set(job_ids)
    output_paths = []

    for i in range(max_polls):
        if not pending:
            break
        logger.info(f"[Poll {i+1}/{max_polls}] Checking {len(pending)} jobs...")
        for job_id in list(pending):
            results, download_url = client.poll_job(job_id)
            status = results['job_status']
            if status == "success":
                logger.info(f"Job {job_id} completed successfully!")
                output_path = client.download_results(job_id, output_dir=output_dir)
                output_paths.append(output_path)
                pending.remove(job_id)
            elif status == "failed":
                logger.error(f"Job {job_id} failed. {results.get('message', 'No error message provided')}")
                pending.remove(job_id)
            else:
                # Job is still processing
                if status == "queued":
                    logger.info(f"Job {job_id} is queued, waiting to start...")
                else:
                    logger.info(f"Job {job_id} is running...")
        time.sleep(poll_interval_seconds)

    return output_paths

def _write_job_ids(job_ids, filename):
    with open(filename, "a") as f:
        for jid in job_ids:
            f.write(f"{jid}\n")
    logger.info(f"All job IDs written to {filename}. Length: {len(job_ids)}")

def _read_all_job_ids(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(job_ids)} existing job IDs from {filename}")
        return job_ids
    else:
        raise FileNotFoundError(f"File {filename} not found")

def _get_zip_paths(root_folder, prefix="output", recursive=True):
    zip_paths = []
    if recursive:
        for root, dirs, files in os.walk(root_folder):
            for file in files:
                if file.startswith(prefix) and file.endswith(".zip"):
                    zip_paths.append(os.path.join(root, file))
    else:
        for file in os.listdir(root_folder):
            if file.startswith(prefix) and file.endswith(".zip"):
                zip_paths.append(os.path.join(root_folder, file))
    logger.info(f"Found {len(zip_paths)} {prefix}*.zip files in {root_folder}")
    return zip_paths
# ============================================================================
# Load configurations from config.yaml
# ============================================================================

config_map = dict(zip(["mmpbsa", "analysis", "simulation"], get_configs("config.yaml")))
api_key = os.getenv("SIMATOMIC_API_KEY")
if not api_key:
    raise SystemExit("Missing SIMATOMIC_API_KEY environment variable.")
client = SimAtomicClient(api_key=api_key)
_base = "absolute/path/to/your/folder/with/all/zipped_structures"
simulation_input_zips = sorted(glob.glob(f"{_base}/*.zip"))
logger.info(f"Found {len(simulation_input_zips)} simulation input zips")


# ============================================================================
# 1. Submit & poll simulation jobs
# ============================================================================
SIMULATION_JOB_IDS_FILE = "simulation_job_ids.txt"
ANALYSIS_JOB_IDS_FILE = "analysis_job_ids.txt"

run_simulation = False
poll_simulation = True
if run_simulation:
    for filepath in simulation_input_zips:
        job_id = submit_jobs(config_map, mode="simulation", filename=filepath)
        _write_job_ids(job_id, SIMULATION_JOB_IDS_FILE)

if poll_simulation:
    simulation_job_ids = _read_all_job_ids(SIMULATION_JOB_IDS_FILE)
    output_paths = poll_jobs(simulation_job_ids, poll_interval_seconds=10, output_dir='/absolute/path/to/your/output/folder')
    logger.info(f"Output paths: {output_paths}")


# ============================================================================
# 2. Create input zip for analysis and mmpbsa
# ============================================================================
analysis = False
if analysis:
    output_paths = _get_zip_paths('/absolute/path/to/your/output/folder')
    for output_path in output_paths:
        basename = os.path.basename(output_path)
        job_id = basename.replace("output_", "").replace(".zip", "")
        create_input_zip(output_path, job_id, "input_analysis", output_dir='/absolute/path/to/your/input/analysis/folder')


# ============================================================================
# 3. Submit & poll simulation jobs
# ============================================================================
run_analysis = False
poll_analysis = False
if run_analysis:
    analysis_input_zips = _get_zip_paths("/absolute/path/to/your/input/analysis/folder", prefix="input_analysis", recursive=False)
    for filepath in analysis_input_zips:
        job_ids = submit_jobs(config_map, mode="analysis", filename=filepath)
        _write_job_ids(job_ids, ANALYSIS_JOB_IDS_FILE)
    
if poll_analysis:
    analysis_job_ids = _read_all_job_ids(ANALYSIS_JOB_IDS_FILE)
    poll_jobs(analysis_job_ids, poll_interval_seconds=20)
