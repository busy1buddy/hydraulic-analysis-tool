import subprocess
import os
import sys

def run_tester():
    print("--- Launching Tester Agent ---")
    # We use pytest to run our agent script
    result = subprocess.run([
        sys.executable, "-m", "pytest", "scripts/tester_agent.py", "-v"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("ERRORS:", result.stderr)
        
    report_path = os.path.join("reports", "tester_feedback.md")
    if os.path.exists(report_path):
        print("\n--- Tester Feedback ---")
        with open(report_path, "r") as f:
            print(f.read())
    else:
        print("\n[!] Tester failed to generate a report.")

if __name__ == "__main__":
    run_tester()
