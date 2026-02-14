#!/usr/bin/env python3
"""
SimAtomic API Client

This module provides a simple interface to interact with the SimAtomic platform
for Molecular Dynamics simulations, MM-PBSA calculations, and trajectory analysis. 
It handles file upload to the cloud storage and retrieves download links for the results
through the SimAtomic REST API.

Requirements:
- Python 3.6+
- requests library
- Valid API key for SimAtomic platform

Usage:
    python simatomic_client.py

Example:
    import simatomic_client
    client = simatomic_client.SimAtomicClient(api_key="1234567890")
    client.run_job("/path/to/trajectory.zip", config)
"""

import os
import sys
import json
import requests
import zipfile
from pathlib import Path
import tempfile
import time
import yaml
import shutil
from urllib.parse import urlparse, unquote
from typing import Tuple

class SimAtomicClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_base_url = "https://app.simatomic.com/api/api_handler/"
        self.api_endpoint_presigned_url = self.api_base_url + "get_presigned_url"
        self.api_endpoint_start_server = self.api_base_url + "start_remote_server"
        self.api_endpoint_queue_job = self.api_base_url + "queue_job"
        self.api_endpoint_get_job_status = self.api_base_url + "poll_job"
        self.api_endpoint_get_download_url = self.api_base_url + "download"
        self.filename = None
        self.file_path = None
        self.job_id_to_input_dir = {}  # Map job_id to input file directory

        # self.api_endpoint_analysis = self.api_base_url + "analyze_trajectory"
        # self.api_endpoint_mmpbsa = self.api_base_url + "mmpbsa"
        # self.api_endpoint_batch_simulation = self.api_base_url + "run_simulation"
        print("""
        ╔══════════════════════════════════════════════════════════════╗
        ║  🧬  SimAtomic Client                                        ║
        ╠══════════════════════════════════════════════════════════════╣
        ║  Usage:                                                      ║
        ║    client.run_job("/path/to/trajectory.zip", config)         ║
        ║                                                              ║
        ║  Config requires 'mode' key: "analysis" | "mmpbsa"           ║
        ║                                                              ║
        ║  Example:                                                    ║
        ║    config = {"mode": "analysis", "atom_selection": "name CA"}║
        ║    client.run_job("trajectory.zip", config)                  ║
        ╚══════════════════════════════════════════════════════════════╝
        """)

    # =============================================================================
    # File Handling
    # =============================================================================
    def _validate_and_upload_files(self, presigned_url_endpoint: str, file_path: str):
        """
        Prepare local path/filename, request a presigned URL, and upload the file.
        Returns True on success. Raises SimAtomicError on failure.
        """
        self._validate_file(file_path)
        presigned_url, job_id = self._request_presigned_url(presigned_url_endpoint)
        self._upload_file(presigned_url)
        return True, job_id


    def _validate_file(self, file_path: str) -> None:
        """
        Validate file path and set local filepath and filename.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        # Store the directory of the input file (empty string if in current directory)
        # Use relative path to preserve directory structure relative to working directory
        self.input_dir = os.path.dirname(file_path) if os.path.dirname(file_path) else ""
        print(f"\n[1/4] Folder found: {self.filename}")
        
        
    def _request_presigned_url(self, api_endpoint: str) -> str:
        """
        Request a presigned URL from SimAtomic for secure file upload.
        """
        # Add filename to params
        if not self.filename:
            raise ValueError("Filename not set")
        payload = {"key": self.filename}

        ok, resp, _ = self._send_request(api_endpoint, payload)

        if not resp["presigned_url"]:
            raise RuntimeError("Failed to get presigned URL")
        print(f"[2/4] Upload URL ready")
        return resp["presigned_url"], resp["job_id"]


    def _upload_file(self, presigned_url: str) -> bool:
        """
        Upload a file to SimAtomic cloud using the presigned URL.
        """
        try:
            with open(self.file_path, "rb") as f:
                resp = requests.put(
                    presigned_url, 
                    data=f, 
                    timeout=300
                    )
                resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to upload file: {e}")
        print(f"[3/4] Folder uploaded")
        return True    


    # =============================================================================
    # Helpers
    # =============================================================================

    def _submit_job(self, api_endpoint: str, params: dict, job_id: str) -> str:
        """
        Request a presigned URL from SimAtomic for secure file upload.
        """
        payload = dict(params) if params else {}
        payload["key"] = self.filename
        payload["job_id"] = job_id
        ok, resp, _ = self._send_request(api_endpoint, payload)
        if not ok:
            raise RuntimeError("Failed to submit job")
        mode = params.get("mode", "unknown")
        print(f"[4/4] Job submitted | mode: {mode} | job_id: {job_id}")
        # print(f"   └── config:")
        # for line in json.dumps(payload, indent=6).split('\n'):
        #     print(f"       {line}")
        return True, resp


    def _start_job(self, api_endpoint: str, params: None) -> str:
        """
        Start a job on the SimAtomic platform.
        """
        ok, resp, _ = self._send_request(api_endpoint, params)
        if not ok:
            raise RuntimeError("Failed to start job")
        return True, resp


    def _send_request(self, endpoint: str, params: dict = None, method: str = "POST") -> Tuple[bool, dict, int]:
        """
        Call the API endpoint and return (ok, response_data, status_code).
        """         
        payload = dict(params) if params else {}
        try:
            resp = requests.post(endpoint, json=payload, headers={"X-API-Key": self.api_key}, timeout=300)
            
            try:
                data = resp.json()
            except ValueError:
                # Response is not JSON - show what we got
                preview = resp.text[:200] if resp.text else "(empty)"
                raise RuntimeError(f"API returned non-JSON (status {resp.status_code}): {preview}")
            
            return resp.ok, data, resp.status_code
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to call API: {e}")

    # =============================================================================
    # API Calls
    # =============================================================================
    def run_job(self, file_path: str, params: dict) -> dict:
        """
        End to end analysis workflow for a trajectory file. Returns the analysis results dict.
        """
        files_ok, job_id = self._validate_and_upload_files(self.api_endpoint_presigned_url, file_path)
        # Store mapping of job_id to input directory for later download
        self.job_id_to_input_dir[job_id] = self.input_dir
        job_ok, response = self._submit_job(self.api_endpoint_queue_job, params, job_id)
        results = self._start_job(self.api_endpoint_start_server, None)
        return job_id


    def poll_job(self, job_id: str, api_endpoint: str = None) -> dict:
        """
        Poll the job status by job_id.
        Returns job_id, job_status, and message.
        """
        if api_endpoint is None:
            api_endpoint = self.api_endpoint_get_job_status
        payload = {"job_id": job_id}
        ok, resp, status_code = self._send_request(api_endpoint, payload)
        download_url = None

        if status_code == 200:
            if resp['job_status'] == "success":
                return resp, job_id  # Return job_id, caller can use download_results(job_id)
            else:
                return resp, None
        elif status_code == 404:
            return {"job_status": "queued", "message": "Job not in database yet"}, None
        else:
            raise RuntimeError(f"Failed to poll job: {status_code}")

    def download_results(self, job_id: str, output_dir: str = None) -> str:
        """
        Download job results by job_id using curl.
        Attempts to keep the original object filename from the redirect target URL.
        Args:
            job_id: The job ID to download results for
            output_dir: Directory path to save the zip file.
                       Default: directory of input file, or current directory if not found.
        Returns the path to the saved file.
        """
        import subprocess
        
        # If no output_dir specified, use the directory of the input file for this job.
        if output_dir is None:
            output_dir = self.job_id_to_input_dir.get(job_id, "")
        
        if not output_dir:
            output_dir = "."
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        url = f"{self.api_endpoint_get_download_url}?job_id={job_id}"

        # Resolve final redirected URL first, then extract filename from its path.
        resolve_cmd = [
            "curl", "-sS", "-L",
            "-o", "/dev/null",
            "-w", "%{url_effective}",
            "-H", f"X-API-Key: {self.api_key}",
            url
        ]
        resolve_result = subprocess.run(resolve_cmd, capture_output=True, text=True)
        if resolve_result.returncode == 0:
            final_url = resolve_result.stdout.strip()
            filename = os.path.basename(unquote(urlparse(final_url).path.rstrip("/")))
        else:
            filename = ""

        if not filename:
            filename = f"output_{job_id}.zip"
        output_path = os.path.join(output_dir, filename)

        cmd = [
            "curl", "-L", "-C", "-",
            "-H", f"X-API-Key: {self.api_key}",
            "-o", output_path,
            "--progress-bar",
            url
        ]

        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download results (curl exit code: {result.returncode})")

        print(f"📁 Downloaded to {output_path}")
        return output_path


    def abort_job(self, job_id: str) -> dict:
        """
        Abort a job by job_id.
        """
        payload = {"job_id": job_id}
        ok, resp, status_code = self._send_request(self.api_endpoint_abort_job, payload)
        if not ok:
            raise RuntimeError("Failed to abort job")
        return resp


# =============================================================================
# Configuration Loading
# =============================================================================

def get_configs(config_path: str):
    """
    Load and return all three configuration dictionaries from config.yaml.
    
    Args:
        config_path: Path to the config.yaml file (required).
    
    Returns:
        tuple: (mmpbsa_parameters, analysis_parameters, simulation_parameters)
    """
    if config_path is None:
        raise ValueError("config_path is required")
    
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config_data = yaml.safe_load(f)
    
    mmpbsa_parameters = config_data.get("mmpbsa_parameters", {})
    analysis_parameters = config_data.get("analysis_parameters", {})
    simulation_parameters = config_data.get("simulation_parameters", {})
    
    return mmpbsa_parameters, analysis_parameters, simulation_parameters


# =============================================================================
# Helper Functions for Creating Input Zips
# =============================================================================

def _extract_simulation_files(simulation_folder: str):
    """Extract and locate required files from simulation results. Returns (files_dict, temp_dir)."""
    sim_path = Path(simulation_folder)
    if not sim_path.exists():
        raise FileNotFoundError(f"Not found: {simulation_folder}")
    
    temp_dir = None
    
    # Extract zip if needed
    if sim_path.suffix.lower() == '.zip':
        temp_dir = tempfile.mkdtemp(prefix="simatomic_extract_")
        print(f"Extracting {sim_path.name}...")
        with zipfile.ZipFile(sim_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        extracted = Path(temp_dir)
        sim_path = None
        if (extracted / "output").exists():
            sim_path = extracted
        else:
            for item in extracted.iterdir():
                if item.is_dir() and (item / "output").exists():
                    sim_path = item
                    break
        if not sim_path:
            shutil.rmtree(temp_dir)
            raise ValueError(f"No 'output' directory found in: {simulation_folder}")
    
    output_path = sim_path / "output"
    prep_dir = output_path / "prep"
    
    # Find trajectory
    traj_matches = list((output_path / "md").glob("final_md_trajectory*.xtc"))
    if not traj_matches:
        raise FileNotFoundError("Trajectory file not found")
    
    # Find emin
    emin = output_path / "emin" / "emin.pdb"
    if not emin.exists():
        raise FileNotFoundError("emin.pdb not found")
    
    # Find topology
    topology_pdb = None
    for name in ["openff_topology.pdb", "openff_interchange.pdb"]:
        if (prep_dir / name).exists():
            topology_pdb = prep_dir / name
            break
    topology_json = prep_dir / "openff_topology.json"
    
    if not topology_pdb and not topology_json.exists():
        raise FileNotFoundError("No topology file found")
    
    # Find md.log
    md_log_matches = list((output_path / "md").glob("md*.log"))
    md_log = md_log_matches[0] if md_log_matches else None

    # Find job_metadata.json (in parent folder of output dir)
    job_metadata_json_matches = list(sim_path.glob("job_metadata*.json"))
    job_metadata_json = job_metadata_json_matches[0] if job_metadata_json_matches else None

    # Find job_metadata.txt (in parent folder of output dir)
    job_metadata_txt_matches = list(sim_path.glob("job_metadata*.txt"))
    job_metadata_txt = job_metadata_txt_matches[0] if job_metadata_txt_matches else None
    
    return {
        "trajectory": traj_matches[0],
        "emin": emin,
        "topology_pdb": topology_pdb,
        "topology_json": topology_json if topology_json.exists() else None,
        "md_log": md_log,
        "job_metadata_json": job_metadata_json,
        "job_metadata_txt": job_metadata_txt,
    }, temp_dir


def _make_zip(output_dir: str, base_name: str, files: list) -> str:
    """Create a zip file with the given files. Adds .zip extension automatically."""
    path = Path(output_dir) / f"{base_name}.zip"
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for src, dst in files:
            zipf.write(str(src), f"{base_name}/{dst}")
            print(f"  Added {base_name}/{dst}")
    print(f"✅ Created {path}")
    return str(path)


def _clean_job_id(job_id: str) -> str:
    """Extract clean job ID from path or job_id string."""
    # Extract filename if it's a path
    job_id = os.path.basename(job_id)
    # Remove common prefixes and extensions
    job_id = job_id.replace("results_", "").replace("_results", "").replace("results", "").replace(".zip", "")
    return job_id


def create_input_zip(simulation_folder: str, job_id: str, folder_name: str, output_dir: str = None) -> str:
    """
    Create input zip for analysis or mmpbsa from simulation results.
    
    Args:
        mode: "analysis" or "mmpbsa" (mmpbsa includes both topology.pdb and topology.json)
    """
  
    files, temp_dir = _extract_simulation_files(simulation_folder)
    try:
        output_dir = output_dir or str(Path(simulation_folder).parent)
        os.makedirs(output_dir, exist_ok=True)
        
        # (source_path, name_in_zip) tuples
        file_list = [
            (files["trajectory"], "final_md_trajectory.xtc"),
            (files["emin"], "emin.pdb"),
        ]
        
        # Analysis: include one topology file (prefer pdb), no md.log or job_metadata
        # MMPBSA: include both topology files, md.log, and job_metadata
       
        file_list.append((files["topology_pdb"], "openff_topology.pdb"))
         
        file_list.append((files["topology_json"], "openff_topology.json"))
        
        file_list.append((files["md_log"], "md.log"))
         
        file_list.append((files["job_metadata_json"], "job_metadata.json"))
           
        file_list.append((files["job_metadata_txt"], "job_metadata.txt"))
        
        base_name = f"{folder_name}_{_clean_job_id(job_id)}"
        return _make_zip(output_dir, base_name, file_list)
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir)


def create_input_analysis_zip(simulation_folder: str, job_id: str, output_dir: str = None) -> str:
    """
    Create a combined input zip with all files for both analysis and mmpbsa, plus md.log.
    
    Includes: trajectory, emin.pdb, topology files (pdb + json), and md.log
    """
    files, temp_dir = _extract_simulation_files(simulation_folder)
    try:
        output_dir = output_dir or str(Path(simulation_folder).parent)
        os.makedirs(output_dir, exist_ok=True)
        
        file_list = [
            (files["trajectory"], "final_md_trajectory.xtc"),
            (files["emin"], "emin.pdb"),
        ]
        
        # Add optional files only if they exist
        if files["md_log"]:
            file_list.append((files["md_log"], "md.log"))
        if files["job_metadata_json"]:
            file_list.append((files["job_metadata_json"], "job_metadata.json"))
        if files["job_metadata_txt"]:
            file_list.append((files["job_metadata_txt"], "job_metadata.txt"))
        
        if files["topology_pdb"]:
            file_list.append((files["topology_pdb"], "openff_topology.pdb"))
        if files["topology_json"]:
            file_list.append((files["topology_json"], "openff_topology.json"))
      
        
        base_name = f"input_analysis_{_clean_job_id(job_id)}"
        return _make_zip(output_dir, base_name, file_list)
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir)
