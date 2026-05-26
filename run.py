import uvicorn
import sys
import os

# Add the workspace directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("--------------------------------------------------")
    print("Starting JobSeeker Multi-Platform Assistant...")
    print("Dashboard will be available at: http://127.0.0.1:8001")
    print("Press Ctrl+C to stop the server.")
    print("--------------------------------------------------")
    
    # Run the FastAPI server
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, reload=True)
