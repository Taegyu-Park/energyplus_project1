import sys
import os
from pathlib import Path

# 1. Configuration of EnergyPlus Paths
# We will search for standard EnergyPlus installation paths on Windows
EP_POSSIBLE_PATHS = [
    r"C:\EnergyPlusV25-2-0",
    r"C:\EnergyPlusV25-1-0",
    r"C:\EnergyPlusV25-0-0",
    r"C:\EnergyPlusV22-2-0",
]

EP_PATH = None
for p in EP_POSSIBLE_PATHS:
    if Path(p).exists():
        EP_PATH = p
        break

if not EP_PATH:
    # Default fallback to V25-2-0
    EP_PATH = r"C:\EnergyPlusV25-2-0"

if EP_PATH not in sys.path:
    sys.path.insert(0, EP_PATH)

try:
    from pyenergyplus.api import EnergyPlusAPI
except ImportError:
    print(f"[Error] Failed to load pyenergyplus module from '{EP_PATH}'.")
    print("Please make sure EnergyPlus is installed and the path is correct.")
    sys.exit(1)

def run_simulation(idf_file_path, epw_file_path=None):
    project_root = Path(__file__).parent.resolve()
    
    # Resolve IDF path
    idf_path = Path(idf_file_path).resolve()
    if not idf_path.exists():
        print(f"[Error] IDF file not found: {idf_path}")
        sys.exit(1)
        
    # Resolve EPW path
    if epw_file_path:
        weather_path = Path(epw_file_path).resolve()
    else:
        # Default Kwangju weather file
        weather_path = project_root / "data" / "KOR_Kwangju.471560_IWEC (1).epw"
        
    if not weather_path.exists():
        print(f"[Error] EPW weather file not found: {weather_path}")
        sys.exit(1)
        
    # Get IDF file name without extension to create the output folder
    idf_name = idf_path.stem
    output_dir = project_root / "runs" / idf_name
    
    # Create the output folder (runs/<idf_name>)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print(f"[Starting EnergyPlus Simulation]")
    print(f"  - IDF File   : {idf_path}")
    print(f"  - EPW Weather: {weather_path}")
    print(f"  - Output Dir : {output_dir}")
    print("=" * 60)
    
    # Initialize the API
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()
    
    # Configure arguments
    arguments = [
        "-d", str(output_dir),
        "-w", str(weather_path),
        str(idf_path)
    ]
    
    # Run simulation
    status = api.runtime.run_energyplus(state, arguments)
    
    # Clean up state
    api.state_manager.delete_state(state)
    
    print("-" * 60)
    if status == 0:
        print(f"[Success] Simulation completed successfully!")
        print(f"Results are saved in: {output_dir}")
    else:
        print(f"[Failure] Simulation failed with exit code: {status}")
        print(f"Check the error log file: {output_dir / 'eplusout.err'}")
    print("=" * 60)
    
    return status

if __name__ == "__main__":
    # Command line argument parser
    if len(sys.argv) > 1:
        idf_file = sys.argv[1]
        epw_file = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        # Default to 260603.idf
        idf_file = "260603.idf"
        epw_file = None
        
    run_simulation(idf_file, epw_file)
