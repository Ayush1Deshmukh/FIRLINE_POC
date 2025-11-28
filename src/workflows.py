from temporalio import workflow
import dataclasses
from datetime import timedelta
import asyncio
from temporalio.common import RetryPolicy

# Call activities by string name to ensure determinism

@workflow.defn
class IncidentWorkflow:
    def __init__(self):
        self.is_approved = False
        self.summary = "Investigation in progress..." # <--- NEW: State variable

    @workflow.signal
    def approve_action(self):
        self.is_approved = True

    # --- NEW: This allows the API to ask "What did you find?" ---
    @workflow.query
    def get_current_summary(self) -> str:
        return self.summary

    @workflow.run
    async def run(self, alert: dict) -> str:
        workflow.logger.info(f"--- 🏁 Workflow started for {alert['service']} ---")

        # 1. Run the Investigation
        investigation_summary = await workflow.execute_activity(
            "run_investigation",
            alert,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # Save the result to our state variable so the UI can see it
        self.summary = investigation_summary

        # 2. WAITING FOR HUMAN APPROVAL
        workflow.logger.info(f"--- 🤖 AI Summary: {investigation_summary} ---")
        workflow.logger.info("--- ✋ Remediation found. WAITING FOR HUMAN APPROVAL... ---")

        # 3. THE PAUSE
        try:
            await workflow.wait_condition(
                lambda: self.is_approved, 
                timeout=timedelta(seconds=120)
            )
        except asyncio.TimeoutError:
            self.summary = "Approval timed out."
            return "Investigation complete. Fix proposed but timed out waiting for approval."

        # 4. Execute Remediation
        workflow.logger.info("--- 👮‍♂️ Approval received! Executing fix... ---")

        execution_result = await workflow.execute_activity(
            "execute_remediation",
            "kubectl rollout undo deployment/auth-service",
            start_to_close_timeout=timedelta(minutes=1)
        )

        final_report = f"{investigation_summary}\n\nACTION TAKEN: {execution_result}"
        self.summary = final_report # Update state with final result

        return final_report