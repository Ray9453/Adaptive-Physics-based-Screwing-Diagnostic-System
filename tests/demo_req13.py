import sys
import os
import pprint
import json
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apsd import APSDiagnosticSystem
from apsd.core.feature_extractor import PhysicalFeatures

def demo_optimization():
    print("--- Demo: Requirement 13 (Percentage Optimization) ---")
    
    # 1. Initialize System
    sdk = APSDiagnosticSystem()
    carrier_id = "DEMO_REQ13_PCT"
    
    # 2. Golden Base (Mean = 5.0)
    print("Step 1: Establishing Golden Base (Mean=5.0)...")
    model = sdk._get_model(carrier_id, "Hole_1")
    for _ in range(100):
        feat = PhysicalFeatures(
            peak_torque=np.random.normal(5.0, 0.05),
            rigidity_slope=1.0, total_work=5.0, seating_angle=10.0, snug_torque=1.0
        )
        model.update(feat)
        
    # 3. Simulate Drop (Mean = 4.5, i.e., -10% change)
    # Also High Variance for speed suggestion
    print("Step 2: Simulating Drift (Mean=4.5) & Instability...")
    for _ in range(200):
        feat = PhysicalFeatures(
            peak_torque=np.random.normal(4.5, 0.5), 
            rigidity_slope=1.0, total_work=5.0, seating_angle=10.0, snug_torque=1.0
        )
        model.update(feat)
        
    # 4. Diagnose
    opt_result = model.get_optimization_suggestion()
    final_output = sdk._assemble_final_dict(model.evaluate(feat), opt_result)
    
    print("\n=== Final JSON Output ===")
    print(json.dumps(final_output["optimization_suggestion"]["params"], indent=2))
    
    params = final_output["optimization_suggestion"]["params"]
    
    # Assertions
    t_adj = params.get("suggested_torque_adjustment_percent")
    s_adj = params.get("suggested_speed_adjustment_percent")
    
    print(f"\nTorque Adj: {t_adj}% (Expected approx -10.0)")
    print(f"Speed Adj: {s_adj}% (Expected -10)")
    
    # Allow some random noise variance
    if -12 < t_adj < -8:
        print("[PASS] Torque Percentage Correct")
    else:
        print("[FAIL] Torque Percentage Out of Range")

if __name__ == "__main__":
    demo_optimization()
