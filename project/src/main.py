from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import socketio
import pdfplumber
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import json
import datetime

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=["http://localhost:5173"])
socket_app = socketio.ASGIApp(sio)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.routers import scan, report, health

app.include_router(scan.router, prefix="/api/scan", tags=["scan"])
app.include_router(report.router, prefix="/api/report", tags=["report"])
app.include_router(health.router, prefix="/api")

@sio.on('scan_progress')
async def emit_scan_progress(scan_id, progress, message):
    """Emit scan progress updates."""
    print(f"📡 Emitting scan progress: {scan_id} - {progress}% - {message}")
    await sio.emit('scan_progress', {'id': scan_id, 'progress': progress, 'message': message})

@sio.on('scan_complete')
async def emit_scan_complete(scan_id, results):
    """Emit scan completion notifications."""
    try:
        # Convert datetime objects to ISO format
        def serialize(obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            elif isinstance(obj, list):
                return [serialize(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: serialize(value) for key, value in obj.items()}
            return obj

        serialized_results = serialize(results)
        print(f"🎯 Scan complete for {scan_id}. Sending results: {serialized_results}")
        await sio.emit('scan_complete', {'id': scan_id, 'results': serialized_results})
    except Exception as e:
        print(f"Error serializing scan results: {e}")

# Add a new function to trigger scan completion and emit results
async def trigger_scan_complete(scan_id, results):
    """Trigger scan completion and notify frontend."""
    print(f"🔔 Triggering scan complete for {scan_id} with results.")
    await emit_scan_complete(scan_id, results)

app.mount("/", socket_app)

@sio.on('connect')
async def connect(sid, environ):
    print(f"✅ Client connected: {sid}")

@sio.on('disconnect')
async def disconnect(sid):
    print(f"❌ Client disconnected: {sid}")

app.mount("/", socket_app)

@sio.on('connect')
async def connect(sid, environ):
    print(f"✅ Client connected: {sid}")

@sio.on('disconnect')
async def disconnect(sid):
    print(f"❌ Client disconnected: {sid}")

# Extract data from the OWASP PDF
def extract_data_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    
    # Extract Risk Levels
    risk_levels = {
        "Critical": text.count("CRITICAL"),
        "High": text.count("HIGH"),
        "Medium": text.count("MEDIUM"),
        "Low": text.count("LOW"),
        "Best Practice": text.count("BEST PRACTICE"),
        "Information": text.count("INFORMATION"),
    }
    
    return text, risk_levels

# Generate Risk Level Chart
def generate_chart(risk_levels):
    labels = list(risk_levels.keys())
    values = list(risk_levels.values())

    plt.figure(figsize=(6, 4))
    plt.bar(labels, values, color=['red', 'orange', 'yellow', 'green', 'blue', 'gray'])
    plt.xlabel("Risk Level")
    plt.ylabel("Number of Issues")
    plt.title("Vulnerabilities Breakdown")
    
    chart_path = "risk_chart.png"
    plt.savefig(chart_path)
    plt.close()
    
    return chart_path

# Generate PDF Report
def generate_pdf(summary_text, risk_levels):
    pdf_path = "OWASP_Report.pdf"
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, height - 50, "OWASP Vulnerability Report")
    
    c.setFont("Helvetica", 12)
    y_position = height - 80
    for line in summary_text.split("\n")[:15]:  # Limit summary text
        c.drawString(30, y_position, line)
        y_position -= 20

    # Insert Chart
    chart_path = generate_chart(risk_levels)
    c.drawImage(chart_path, 100, y_position - 150, width=300, height=200)
    
    c.save()
    os.remove(chart_path)
    
    return pdf_path

@app.post("/api/report/generate")
async def generate_report(file: UploadFile):
    try:
        # Save uploaded file temporarily
        temp_file_path = f"temp_{file.filename}"
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(await file.read())

        # Extract data and generate report
        summary_text, risk_levels = extract_data_from_pdf(temp_file_path)
        pdf_file = generate_pdf(summary_text, risk_levels)

        # Clean up temporary file
        os.remove(temp_file_path)

        return FileResponse(pdf_file, media_type="application/pdf", filename="OWASP_Report.pdf")
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000)
