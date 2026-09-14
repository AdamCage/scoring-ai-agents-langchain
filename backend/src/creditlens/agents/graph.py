from __future__ import annotations

from typing import Any

from contracts.state import CreditState
from langgraph.graph import END, START, StateGraph

from creditlens.agents.nodes import (
    calculate_score,
    explain_score,
    human_review,
    policy_critic,
    request_information,
    retrieve_more,
    retrieve_policy_node,
    risk_analysis,
    route_after_critic,
    route_after_validation,
    synthesize,
    validate_application,
)


def build_graph() -> Any:
    builder = StateGraph(CreditState)
    builder.add_node("validate_application", validate_application)
    builder.add_node("request_information", request_information)
    builder.add_node("calculate_score", calculate_score)
    builder.add_node("explain_score", explain_score)
    builder.add_node("retrieve_policy", retrieve_policy_node)
    builder.add_node("risk_analysis", risk_analysis)
    builder.add_node("policy_critic", policy_critic)
    builder.add_node("retrieve_more", retrieve_more)
    builder.add_node("synthesize", synthesize)
    builder.add_node("human_review", human_review)

    builder.add_edge(START, "validate_application")
    builder.add_conditional_edges(
        "validate_application",
        route_after_validation,
        {
            "request_information": "request_information",
            "calculate_score": "calculate_score",
        },
    )
    builder.add_edge("request_information", END)
    builder.add_edge("calculate_score", "explain_score")
    builder.add_edge("calculate_score", "retrieve_policy")
    builder.add_edge("explain_score", "risk_analysis")
    builder.add_edge("retrieve_policy", "risk_analysis")
    builder.add_edge("risk_analysis", "policy_critic")
    builder.add_conditional_edges(
        "policy_critic",
        route_after_critic,
        {
            "retrieve_more": "retrieve_more",
            "synthesize": "synthesize",
        },
    )
    builder.add_edge("retrieve_more", "risk_analysis")
    builder.add_edge("synthesize", "human_review")
    builder.add_edge("human_review", END)
    return builder.compile()


GRAPH = None


def get_graph():
    global GRAPH
    if GRAPH is None:
        GRAPH = build_graph()
    return GRAPH
