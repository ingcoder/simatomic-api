#!/usr/bin/env python3
"""
Minimal SimAtomic "simulation" example.

Usage:
  SIMATOMIC_API_KEY=... python3 basic_simulation.py /path/to/input_simulation.zip
"""

import os
import time
from pathlib import Path
from simatomic_client import SimAtomicClient, get_configs


def main():
    client = SimAtomicClient(api_key="123-your-api-key-here")
    input_zip_path = "/Users/ingrid/Projects/SimAtomicAPI/ppkib/input_sim_dataset_zips/1AXC.zip"
    job_id = client.run_job(str(input_zip_path), {"mode": "simulation", "md_steps": 100})
    print(f"Submitted simulation job: {job_id}")

    while True:
        result, done_job_id = client.poll_job(job_id)
        status = result.get("job_status")
        message = result.get("message")
        print(f"status={status} message={message}")

        if done_job_id:
            output_path = client.download_results(job_id)
            print(f"Downloaded: {output_path}")

        if status == "failed":
            raise Exception(f"Simulation job failed: {message}")

        time.sleep(20)


if __name__ == "__main__":
    main()
