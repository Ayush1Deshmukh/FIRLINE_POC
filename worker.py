import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

# 1. IMPORT YOUR NEW WORKFLOW AND ACTIVITY
from src.workflows import IncidentWorkflow
from src.activities import run_investigation

async def main():
    print("--- 👟 Temporal Worker starting... ---")
    # Connect to the local Temporal server
    client = await Client.connect("127.0.0.1:7233")

    # 2. CREATE THE WORKER
    # This worker connects to Temporal and "listens"
    # on a specific "task queue" for jobs.
    worker = Worker(
        client,
        task_queue="fireline-task-queue", # <-- This name must match the API
        workflows=[IncidentWorkflow],    # <-- Tell it about your workflow
        activities=[run_investigation],  # <-- Tell it about your activity
    )
    print("--- ✅ Temporal Worker connected and listening on 'fireline-task-queue' ---")

    # 3. RUN THE WORKER
    # This will run forever until you press CTRL+C
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())