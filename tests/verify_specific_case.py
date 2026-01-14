import sys
import os
import pprint
import shutil

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apsd import APSDiagnosticSystem

def run_specific_verification():
    # Setup clean environment
    model_dir = "tests/specific_case_models"
    if os.path.exists(model_dir):
        shutil.rmtree(model_dir) # Start fresh
    
    sdk = APSDiagnosticSystem(config_path="configs/default_config.yaml", model_dir=model_dir)

    # Payload provided by user
    payload = {
        "[1]1": {
            "torque": [0.0, 0.5, 1.2, 2.8, 4.5, 5.0],
            "angle": [0.0, 10.5, 45.0, 90.0, 150.0, 180.0],
            "time": [0.01, 0.05, 0.12, 0.25, 0.45, 0.60]
        },
        "[1]2": {
            "torque": [0.0, 0.2, 0.5, 0.8, 1.0, 1.2],
            "angle": [0.0, 20.0, 60.0, 120.0, 240.0, 360.0],
            "time": [0.01, 0.10, 0.25, 0.50, 0.80, 1.10]
        }
    }

    print("Running Diagnose on CARRIER_2026_001...")
    results = sdk.diagnose(carrier_id="CARRIER_2026_001", data=payload)
    
    print("\n=== Specific Case Results ===")
    pprint.pprint(results)

    # Basic assertions
    # Since this is Cold Start (N=1) and hard constraints seem satisfied (positive slope, torque rise), 
    # we expect OK unless Slope is super weird.
    # [1]2 is very loose/low torque, but physically "possible" (just soft).
    
    return results

if __name__ == "__main__":
    run_specific_verification()
