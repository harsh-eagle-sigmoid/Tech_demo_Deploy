"""
Monitor ground truth generation and run evaluation test when complete
"""
import time
import subprocess
import os
from loguru import logger

logger.add("logs/monitor.log", rotation="10 MB")

def check_ground_truth_complete():
    """Check if ground truth generation is complete"""
    try:
        # Check if all_queries.json exists and has data
        if os.path.exists('data/ground_truth/all_queries.json'):
            import json
            with open('data/ground_truth/all_queries.json', 'r') as f:
                queries = json.load(f)
            if len(queries) >= 1000:
                return True, len(queries)
        return False, 0
    except:
        return False, 0

def monitor_progress():
    """Monitor ground truth generation progress"""
    print("🔍 Monitoring ground truth generation...")
    print("=" * 80)

    last_count = 0
    checks = 0

    while True:
        checks += 1

        # Check if complete
        is_complete, count = check_ground_truth_complete()

        if is_complete:
            print(f"\n✅ Ground truth generation complete! {count} queries generated.")
            return True

        # Check progress from log file
        try:
            result = subprocess.run(
                ["grep", "Generated.*queries", "/tmp/claude-1000/-home-lenovo-Desktop-New-tech-demo/tasks/b0fdc29.output"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    last_line = lines[-1]
                    # Extract number
                    import re
                    match = re.search(r'Generated (\d+) queries', last_line)
                    if match:
                        current_count = int(match.group(1))
                        if current_count != last_count:
                            progress = (current_count / 1000) * 100
                            print(f"[{checks:03d}] Progress: {current_count}/1000 queries ({progress:.1f}%)")
                            last_count = current_count
        except:
            pass

        # Wait before next check
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    try:
        # Monitor until complete
        if monitor_progress():
            print("\n" + "=" * 80)
            print("🧪 Starting Evaluation Test...")
            print("=" * 80 + "\n")

            # Run evaluation test
            result = subprocess.run(
                ["venv/bin/python", "-m", "evaluation.test_evaluator"],
                cwd="/home/lenovo/Desktop/New_tech_demo"
            )

            if result.returncode == 0:
                print("\n✅ Evaluation test completed successfully!")
            else:
                print(f"\n❌ Evaluation test failed with code {result.returncode}")

    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring stopped by user")
