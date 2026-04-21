import subprocess
import os
import sys
import time

def run_verification():
    print("[*] Running Autonomous Navigation Verification...")
    
    # Ensure binterint is installed or in path
    # For testing, we call it via python -m binterint.cli
    cmd = [
        sys.executable, "-m", "binterint.cli", "auto",
        "python sample_tui.py",
        "--goal", "Click on Button 1 and finally exit",
        "--max-steps", "10"
    ]
    
    print(f"[*] Executing: {' '.join(cmd)}")
    try:
        # Run the auto command
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("[+] Auto-session output:")
        print(result.stdout)
        
        # Check for screenshots
        for i in range(1, 4): # Expecting at least a few steps
            path = f"auto_step_{i}.png"
            if os.path.exists(path):
                print(f"[+] Found step screenshot: {path}")
            else:
                print(f"[-] Missing step screenshot: {path}")

        print("\n[+] Verification Complete.")
        
    except subprocess.CalledProcessError as e:
        print(f"[!] Auto-session failed with exit code {e.returncode}")
        print("[!] Error output:")
        print(e.stderr)
        print("[!] Standard output:")
        print(e.stdout)

if __name__ == "__main__":
    run_verification()
