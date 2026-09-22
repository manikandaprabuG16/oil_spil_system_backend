"""
Oil Spill Intelligence System - FastAPI Launcher
SIH26143: Satellite Imagery + AIS for Oil-Spill Attribution
Configured for both Local Execution and Render Cloud Deployment.
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    print("=========================================================================")
    print("  SIH26143: OIL SPILL INTELLIGENCE SYSTEM (BACKEND API)")
    print(f"  Starting FastAPI server on http://{host}:{port} ...")
    print("=========================================================================")
    uvicorn.run("backend.app:app", host=host, port=port, reload=False)
