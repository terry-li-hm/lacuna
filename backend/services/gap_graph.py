import asyncio
import operator
import uuid
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import NotRequired, TypedDict

from langgraph.types import Send, interrupt
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver

from backend.models.schemas import GapRequirementMapping, Provenance

CompiledGraph = CompiledStateGraph


class GapState(TypedDict):
    circular_doc_id: str
    baseline_id: str
    requirements: List[Dict[str, Any]]
    current_req: Optional[Dict[str, Any]]
    findings: Annotated[List[GapRequirementMapping], operator.add]
    interactive: NotRequired[bool]
    include_amendments: bool
    no_llm: bool
    vector_store: Any
    llm_service: Any


async def analyze_requirement_node(state: GapState) -> Dict[str, List[GapRequirementMapping]]:
    req = state["current_req"] or {}
    baseline_id = state["baseline_id"]

    baseline_chunks = state["vector_store"].query(
        query_text=req.get("description", ""),
        n_results=3,
        filters={"doc_id": baseline_id},
    )

    analysis = await asyncio.to_thread(
        state["llm_service"].perform_gap_analysis,
        req,
        baseline_chunks,
        state["no_llm"],
    )

    status = analysis.get("status", "Gap")
    draft_amendment: Optional[str] = None
    if state["include_amendments"] and not state["no_llm"] and status in ("Partial", "Gap"):
        draft_amendment = await asyncio.to_thread(
            state["llm_service"].generate_draft_amendment,
            req,
            baseline_chunks,
            status,
            analysis.get("reasoning", "No reasoning provided"),
        )

    finding = GapRequirementMapping(
        circular_req_id=str(uuid.uuid4()),
        description=req.get("description", "No description"),
        status=status,
        reasoning=analysis.get("reasoning", "No reasoning provided"),
        draft_amendment=draft_amendment,
        provenance=[Provenance(**p) for p in analysis.get("provenance", [])],
    )
    return {"findings": [finding]}


def route_requirements(state: GapState) -> List[Send]:
    return [
        Send("analyze_requirement", {**state, "current_req": req})
        for req in state["requirements"]
    ]


def human_review_node(state: GapState) -> dict:
    # Pause for human review when interactive=True; no-op otherwise
    if state.get("interactive"):
        interrupt("Pause for human review — approve findings before generating report")
    return {}


def build_gap_graph(checkpointer=None) -> CompiledGraph:
    """Build the gap analysis graph.

    Pass a checkpointer (e.g. MemorySaver()) to enable interrupt/resume.
    Pass None (default) for test use — graph runs without persistence.
    """
    graph = StateGraph(GapState)
    graph.add_node("analyze_requirement", analyze_requirement_node)
    graph.add_node("human_review_node", human_review_node)
    graph.add_conditional_edges(START, route_requirements, ["analyze_requirement"])
    graph.add_edge("analyze_requirement", "human_review_node")
    graph.add_edge("human_review_node", END)
    return graph.compile(checkpointer=checkpointer)
