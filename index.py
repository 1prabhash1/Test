import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AIAutomationEngine")


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------
@dataclass
class WorkflowContext:
    """Carries dynamic state and execution metadata across workflow steps."""
    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    payload: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Abstract Base Class for Steps
# ---------------------------------------------------------------------------
class BaseStep:
    """Base interface for all automation pipeline steps."""

    def __init__(self, name: str):
        self.name = name

    async def execute(self, context: WorkflowContext) -> WorkflowContext:
        raise NotImplementedError("Steps must implement the execute method.")


# ---------------------------------------------------------------------------
# Concrete AI / Automation Steps
# ---------------------------------------------------------------------------
class IngestionStep(BaseStep):
    """Simulates fetching or ingesting raw operational data."""

    def __init__(self, name: str, source_data: Dict[str, Any]):
        super().__init__(name)
        self.source_data = source_data

    async def execute(self, context: WorkflowContext) -> WorkflowContext:
        logger.info(f"[{self.name}] Ingesting data from source...")
        await asyncio.sleep(0.5)  # Simulate network latency
        context.payload.update(self.source_data)
        logger.info(f"[{self.name}] Ingested {len(self.source_data)} fields.")
        return context


class SentimentAnalysisAIStep(BaseStep):
    """Simulates an AI model call to evaluate sentiment and topic."""

    async def _mock_llm_inference(self, text: str) -> Dict[str, Any]:
        await asyncio.sleep(1.0)  # Simulate API inference call
        text_lower = text.lower()
        if "great" in text_lower or "love" in text_lower:
            sentiment = "positive"
            score = 0.92
        elif "issue" in text_lower or "bug" in text_lower or "broken" in text_lower:
            sentiment = "negative"
            score = 0.85
        else:
            sentiment = "neutral"
            score = 0.50

        return {
            "sentiment": sentiment,
            "confidence": score,
            "summary": text[:50] + "..." if len(text) > 50 else text
        }

    async def execute(self, context: WorkflowContext) -> WorkflowContext:
        logger.info(f"[{self.name}] Processing payload with AI model...")
        input_text = context.payload.get("user_feedback", "")
        
        if not input_text:
            context.errors.append(f"{self.name}: Missing 'user_feedback' in payload.")
            return context

        ai_output = await self._mock_llm_inference(input_text)
        context.results["ai_analysis"] = ai_output
        logger.info(f"[{self.name}] Sentiment analysis complete: {ai_output['sentiment']}")
        return context


class DecisionRoutingStep(BaseStep):
    """Evaluates AI insights and routes execution dynamically."""

    def __init__(self, name: str, action_map: Dict[str, Callable[[WorkflowContext], Any]]):
        super().__init__(name)
        self.action_map = action_map

    async def execute(self, context: WorkflowContext) -> WorkflowContext:
        logger.info(f"[{self.name}] Evaluating routing rules...")
        ai_data = context.results.get("ai_analysis", {})
        sentiment = ai_data.get("sentiment", "neutral")

        action = self.action_map.get(sentiment)
        if action:
            logger.info(f"[{self.name}] Routing triggered for branch: '{sentiment}'")
            if asyncio.iscoroutinefunction(action):
                await action(context)
            else:
                action(context)
        else:
            logger.warning(f"[{self.name}] No specific action found for: '{sentiment}'")

        return context


# ---------------------------------------------------------------------------
# Workflow Orchestrator
# ---------------------------------------------------------------------------
class AutomationPipeline:
    """Orchestrates step execution with error handling and status tracking."""

    def __init__(self, name: str):
        self.name = name
        self.steps: List[BaseStep] = []

    def add_step(self, step: BaseStep) -> "AutomationPipeline":
        self.steps.append(step)
        return self

    async def run(self, initial_payload: Optional[Dict[str, Any]] = None) -> WorkflowContext:
        context = WorkflowContext(payload=initial_payload or {})
        logger.info(f"Starting Workflow [{self.name}] ID: {context.workflow_id}")

        for step in self.steps:
            try:
                context = await step.execute(context)
                if context.errors:
                    logger.error(f"Errors encounterd in step [{step.name}]: {context.errors}")
            except Exception as e:
                logger.exception(f"Unhandled exception during step [{step.name}]: {e}")
                context.errors.append(f"Fatal error at step {step.name}: {str(e)}")
                break

        logger.info(f"Finished Workflow [{self.name}]. Success: {len(context.errors) == 0}")
        return context


# ---------------------------------------------------------------------------
# Handler Actions for Routing
# ---------------------------------------------------------------------------
async def handle_negative_feedback(context: WorkflowContext) -> None:
    logger.info("ACTION: Escalating negative feedback to customer support ticket system.")
    context.results["routed_action"] = "Created high-priority support ticket."

async def handle_positive_feedback(context: WorkflowContext) -> None:
    logger.info("ACTION: Logging positive review for public feedback highlight.")
    context.results["routed_action"] = "Logged into promotional campaign queue."


# ---------------------------------------------------------------------------
# Main Execution Entry Point
# ---------------------------------------------------------------------------
async def main():
    sample_data = {
        "user_id": "usr_9021",
        "user_feedback": "I love the new UI update! It makes automation so easy and fast."
    }

    # Build Pipeline
    pipeline = AutomationPipeline(name="AI Customer Feedback Processor")
    
    pipeline.add_step(
        IngestionStep(name="Data Ingestion", source_data=sample_data)
    ).add_step(
        SentimentAnalysisAIStep(name="AI Processing")
    ).add_step(
        DecisionRoutingStep(
            name="Action Router",
            action_map={
                "negative": handle_negative_feedback,
                "positive": handle_positive_feedback
            }
        )
    )

    # Execute Pipeline
    result_context = await pipeline.run()

    # Display Execution Summary
    print("\n--- Final Workflow Execution Summary ---")
    print(f"Workflow ID: {result_context.workflow_id}")
    print(f"Results: {result_context.results}")
    print(f"Errors: {result_context.errors}")


if __name__ == "__main__":
    asyncio.run(main())
