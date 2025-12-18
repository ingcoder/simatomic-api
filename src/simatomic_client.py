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

class SimAtomicClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_base_url = "https://app.simatomic.com/api/api_handler/"
        self.api_endpoint_presigned_url = self.api_base_url + "get_presigned_url"
        self.api_endpoint_start_server = self.api_base_url + "start_remote_server"
        self.api_endpoint_queue_job = self.api_base_url + "queue_job"
        self.api_endpoint_get_job_status = self.api_base_url + "poll_job"
        self.filename = None
        self.file_path = None

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
        presigned_url = self._request_presigned_url(presigned_url_endpoint)
        self._upload_file(presigned_url)
        return True


    def _validate_file(self, file_path: str) -> None:
        """
        Validate file path and set local filepath and filename.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        print(f"\n[1/4] File validated: {self.filename}")
        
        
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
        return resp["presigned_url"]


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
        
        print(f"[3/4] Uploaded to cloud")
        return True    


    # =============================================================================
    # Helpers
    # =============================================================================

    def _submit_job(self, api_endpoint: str, params: dict) -> str:
        """
        Request a presigned URL from SimAtomic for secure file upload.
        """
        payload = dict(params) if params else {}
        payload["key"] = self.filename
        ok, resp, _ = self._send_request(api_endpoint, payload)
        if not ok:
            raise RuntimeError("Failed to submit job")
        mode = params.get("mode", "unknown")
        job_id = resp.get("message_id", "unknown")
        print(f"[4/4] Job submitted | mode: {mode} | job_id: {job_id}")
        print(f"   └── config:")
        for line in json.dumps(payload, indent=6).split('\n'):
            print(f"       {line}")
        return True, resp


    def _start_job(self, api_endpoint: str, params: None) -> str:
        """
        Start a job on the SimAtomic platform.
        """
        ok, resp, _ = self._send_request(api_endpoint, params)
        if not ok:
            raise RuntimeError("Failed to start job")
        print(f"\n✅ Job is running... polling for results.")
        return True, resp


    def _send_request(self, endpoint: str, params: dict = None, method: str = "POST") -> tuple[bool, dict, int]:
        """
        Call the API endpoint and return (ok, response_data, status_code).
        """         
        payload = dict(params) if params else {}
        try:
          
            resp = requests.post(endpoint, json=payload, headers={"X-API-Key": self.api_key}, timeout=300)
            
            if resp.ok:
                return True, resp.json(), resp.status_code
            else:
                data = resp.json() if resp.text else {}
                return False, data, resp.status_code
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to call API: {e}")

    # =============================================================================
    # API Calls
    # =============================================================================
    def run_job(self, file_path: str, params: dict) -> dict:
        """
        End to end analysis workflow for a trajectory file. Returns the analysis results dict.
        """
        files_ok = self._validate_and_upload_files(self.api_endpoint_presigned_url, file_path)
        job_ok, response = self._submit_job(self.api_endpoint_queue_job, params)
        results = self._start_job(self.api_endpoint_start_server, None)
        return response['message_id']


    def poll_job(self, job_id: str, api_endpoint: str = None) -> dict:
        """
        Poll the job status by job_id.
        Returns job_id, job_status, and message.
        """
        if api_endpoint is None:
            api_endpoint = self.api_endpoint_get_job_status
        payload = {"job_id": job_id}
        ok, resp, status_code = self._send_request(api_endpoint, payload)

        if status_code == 200:
            return resp
        elif status_code == 404:
            print(f"⏳ Job {job_id[:8]}... not found yet (waiting...)")
            return {"job_status": "queued", "message": "Job not in database yet"}
        else:
            raise RuntimeError(f"Failed to poll job: {status_code}")
     
if __name__ == "__main__":
    mmpbsa_parameters = {
            "mode": "mmpbsa",
            "mmpbsa_stride": 100,          # stride when converting traj -> nc
            "mmpbsa_startframe": 0,
            "mmpbsa_endframe": 1000,
            "mmpbsa_interval": 100,
            "igb": 5,                        # 5 or 8 are common for PPIs
            "use_decomp": False,                            # set True if you want per-residue decomposition
            "decomp_idecomp": 3,
            "strip_mask_input": ":HOH:NA:CL",   # used in mmpbsa.in
            "strip_mask_items":[":HOH", ":NA", ":CL"],   # used for ante-MMPBSA -s
            "ligand_chain_mask": ":100-1110",                # ":121-134"  
    }

    ensemble_analysis_parameters = {
            "mode": "analysis",
            "start_frame": 0,
            "atom_selection": "name CA",
            "tica_lag_time": 30,
            "tica_dimensions": 5,
            "min_cluster_size": 10,
            "min_samples": 10,
            "autocorr_maxtime": None,
            "autocorr_threshold": 0.0,
            "autocorr_component": 4,
            "ensemble_output_path": "ensemble_analysis_dashboard.html",
            "rmsd_output_path": "protein_ligand_rmsd_plots.html",
    }

    simulation_parameters = {
        "mode": "simulation"
    }


    analysis_input_path = "path/to/analysis_input.zip"
    mmpbsa_input_path = "path/to/mmpbsa_input.zip"
    simulation_input_path = "path/to/simulation_input.zip"
    
    client = SimAtomicClient(api_key="1234567890") # options: "mmpbsa", "analysis", "batch_simulation"   
    job_id = client.run_job(mmpbsa_input_path, mmpbsa_parameters)
 
    for i in range(100):
        print(f"Polling job {i+1} of 10")
        results = client.poll_job(job_id)
        if results['job_status'] == "success":
            print(f"Job {job_id} completed successfully")
            print(f"Results: {result['message']}")
            break
        elif results['job_status'] == "failed":
            print(f"Job {job_id} failed")
            break
        else:
            if results['job_status'] == "queued":
                print(f"Job {job_id} is queued")
            else:
                print(f"Job {job_id} is running")
            time.sleep(30)


