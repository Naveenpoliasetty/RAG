import subprocess

def run_command(command: str):
    print(f"\n🚀 Running: {command}\n")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        print(f"❌ Command failed: {command}")
        exit(result.returncode)
    print(f"✅ Completed: {command}\n")


if __name__ == "__main__":
    # First command
    run_command("python -m src.data_acquisition.run_data_scraping")

    # Second command
    run_command("python -m src.resume_ingestion.main")

    print("🎉 All tasks completed successfully!")