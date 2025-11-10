from fastapi import FastAPI
from pydantic import BaseModel, Field
from temporalio.client import Client # <-- 1. IMPORT THE TEMPORAL CLIENT
from src.workflows import IncidentWorkflow # <-- Import your workflow

# --- TEMPORAL CLIENT SETUP ---
temporal_client = None

app = FastAPI(
    title="Fireline API",
    description="API for the Fireline SRE Incident Commander"
)

@app.on_event("startup")
async def startup_event():
    """On API startup, connect to the Temporal server."""
    global temporal_client
    temporal_client = await Client.connect("127.0.0.1:7233")
    print("--- 🚀 API: Connected to Temporal server ---")


# (The 'Alert' Pydantic model stays exactly the same)
class Alert(BaseModel):
    timestamp: str = Field(..., example="2025-10-21T03:05:00Z")
    service: str = Field(..., example="auth-service")
    error_message: str = Field(..., example="High CPU Utilization")

@app.get("/")
def read_root():
    """A simple endpoint to check if the API is online."""
    return {"status": "Fireline API is running"}

# 4. UPDATE THE WEBHOOK ENDPOINT
@app.post("/webhook/alert")
async def post_new_alert(alert: Alert): # <-- 3. Make 'async', remove BackgroundTasks
    """
    Receives an alert and starts a durable Temporal workflow.
    """

    print(f"--- 🚀 API: New alert received for {alert.service} ---")

    # 4. THIS IS THE NEW LOGIC
    # We are "starting" a workflow, which is like sending
    # that certified letter.
    await temporal_client.start_workflow(
        # The name of the workflow class
        IncidentWorkflow.run, # <-- Use the run method
        # The arguments to pass to the workflow's run method
        alert.model_dump(),
        # A unique ID for this specific investigation
        id=f"incident-workflow-{alert.service}-{alert.timestamp}",
        # The "task queue" our Worker is listening on
        task_queue="fireline-task-queue",
    )

    # We still return immediately!
    return {"status": "investigation_workflow_started"}