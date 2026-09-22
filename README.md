# Oil Spill Intelligence System - Backend Service

High-performance FastAPI service powering the **SIH26143 Maritime Oil Spill Attribution Intelligence System**.

## Features
- **Satellite SAR & Optical Analysis Engine:** Automated thresholding and contour-based oil slick detection.
- **Dynamic AIS Backtracking:** Fay spreading physics model + wind/current hydrodynamic drift integration.
- **Attribution & Ranking:** Multi-criteria vessel correlation engine.
- **Forensic PDF Dossier Generator:** Automated official investigation reports.
- **Maritime Defense Authentication:** Single operator ID enforcement with 30-minute session auto-lock.

---

## Deploy to Render (Cloud)

1. Sign in to [Render](https://render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository: `https://github.com/manikandaprabuG16/oil_spil_system_backend.git`
4. Configure:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
5. *(Optional)* Add Environment Variables under **Environment**:
   - `AUTH_OPERATOR_ID`: `ICG-COMMAND-01`
   - `AUTH_PASSWORD`: `Maritime@2026`
6. Click **Create Web Service**.

Once deployed, copy your Render service URL (e.g. `https://oil-spill-intelligence-backend.onrender.com`).
