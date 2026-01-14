import numpy as np

def generate_fastening_curve(mode="normal"):
    """
    Simulate torque/angle/time data for different scenarios.
    
    Args:
        mode (str): 'normal', 'loose', 'drift', 'hard_ng_slope', 'hard_ng_torque'
        
    Returns:
        dict: {'torque': [...], 'angle': [...], 'time': [...]}
    """
    # Base time and angle
    steps = 100
    time = np.linspace(0, 2.0, steps)
    angle = np.linspace(0, 360, steps)
    
    # Sigmoid function for S-curve simulation
    def sigmoid(t, k=5, t0=1):
        return 1 / (1 + np.exp(-k * (t - t0)))

    if mode == "normal":
        # Normal S-curve: Peak ~5Nm
        torque = 5 * sigmoid(time, k=10, t0=1.0)
        # Add slight noise
        torque += np.random.normal(0, 0.05, steps)
        
    elif mode == "loose":
        # Low slope/Low torque: Peak ~2Nm (Stripped thread)
        torque = 2 * sigmoid(time, k=5, t0=1.0)
        torque += np.random.normal(0, 0.05, steps)
        
    elif mode == "drift":
        # Simulate aging - slightly higher torque/different characteristics
        # Peak ~6Nm
        torque = 6.0 * sigmoid(time, k=10, t0=1.0)
        torque += np.random.normal(0, 0.05, steps)
        
    elif mode == "hard_ng_slope":
        # Negative slope simulation (Torque drops as angle increases)
        # First goes up, then drops significantly
        torque = 5 * sigmoid(time, k=10, t0=0.5)
        # Force drop in the middle
        torque[50:] = torque[50:] * np.linspace(1, 0.5, 50)
        
    elif mode == "hard_ng_torque":
        # No torque rise (flat)
        torque = np.ones(steps) * 0.1
        
    else:
        # Default normal
        torque = 5 * sigmoid(time, k=10, t0=1.0)

    # Ensure no negative values after noise
    torque = np.maximum(torque, 0)

    return {
        "torque": torque.tolist(),
        "angle": angle.tolist(),
        "time": time.tolist()
    }
