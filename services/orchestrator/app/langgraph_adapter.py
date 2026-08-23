"""Optional LangGraph runtime boundary.

LangGraph is deliberately imported only inside this isolated service. The source
MVP stays runnable without network-installed packages; production CI must install
the exact approved lock and run the contract tests against this adapter.
"""


def build_graph(nodes: dict, edges: list[tuple[str, str]]):
    try:
        from langgraph.graph import StateGraph
    except ImportError as exc:
        raise RuntimeError("LANGGRAPH_NOT_INSTALLED_OR_NOT_APPROVED") from exc
    graph = StateGraph(dict)
    for name, fn in nodes.items():
        graph.add_node(name, fn)
    for source, target in edges:
        graph.add_edge(source, target)
    return graph.compile()
