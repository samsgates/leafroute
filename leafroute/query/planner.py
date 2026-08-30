from __future__ import annotations

from leafroute.models import OperatorName, QueryIR, RetrievalOperator, RetrievalPlan


class RetrievalPlanner:
    def plan(self, query: QueryIR, top_k: int = 5) -> RetrievalPlan:
        ops: list[RetrievalOperator] = []

        if query.metrics:
            ops.append(RetrievalOperator(name=OperatorName.SEARCH_METRIC, args={"values": query.metrics}))
        if query.entities:
            ops.append(RetrievalOperator(name=OperatorName.SEARCH_ENTITY, args={"values": query.entities}))
        if query.dates or query.periods:
            ops.append(RetrievalOperator(name=OperatorName.SEARCH_DATE, args={"values": query.dates + query.periods}))
        if query.requires_table:
            ops.append(RetrievalOperator(name=OperatorName.SEARCH_TABLE, args={}))
        ops.append(RetrievalOperator(name=OperatorName.SEARCH_TEXT, args={"query": query.query}))

        if query.requires_comparison:
            ops.append(RetrievalOperator(name=OperatorName.TEMPORAL_JOIN, args={"periods": query.dates + query.periods}))
        if query.requires_multiple_evidence:
            ops.append(RetrievalOperator(name=OperatorName.EXPAND_PARENT, args={"levels": 1}))
        ops.append(RetrievalOperator(name=OperatorName.RANK, args={}))
        ops.append(RetrievalOperator(name=OperatorName.TOP_K, args={"k": top_k}))
        ops.append(RetrievalOperator(name=OperatorName.READ, args={}))

        return RetrievalPlan(query_ir=query, operators=ops, estimated_llm_calls=0)
