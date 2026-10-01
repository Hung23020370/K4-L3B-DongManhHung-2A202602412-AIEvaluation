"""
Day 14 — AI Evaluation & Benchmarking Pipeline
AICB-P1: AI Practical Competency Program, Phase 1
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Task 1 — Data Models (Golden Dataset + Evaluation Results)
# ---------------------------------------------------------------------------

class QAPair:
    """
    A question-answer pair for evaluation (part of the Golden Dataset).
    Compatible with both keyword args and positional args:
    QAPair(question, expected_answer, context="", metadata=None, retrieved_contexts=None)
    """
    def __init__(
        self,
        question: str = "",
        expected_answer: str = "",
        context: str | None = "",
        metadata: dict[str, Any] | None = None,
        retrieved_contexts: list[str] | None = None,
    ) -> None:
        self.question = question
        self.expected_answer = expected_answer
        self.context = "" if context is None else context
        self.metadata = metadata if metadata is not None else {}
        self.retrieved_contexts = retrieved_contexts if retrieved_contexts is not None else []

    def __repr__(self) -> str:
        return f"QAPair(question={self.question!r}, expected_answer={self.expected_answer!r})"


class EvalResult:
    """
    Evaluation result for a single Q&A pair.
    Compatible with both keyword args and positional args used across tests.
    """
    def __init__(
        self,
        qa_pair: QAPair,
        actual_answer: str = "",
        faithfulness: float = 0.0,
        relevance: float = 0.0,
        completeness: float = 0.0,
        passed: bool = False,
        failure_type: str | None = None,
        context_precision: float | None = None,
        context_recall: float | None = None,
    ) -> None:
        self.qa_pair = qa_pair
        self.actual_answer = actual_answer
        self.faithfulness = float(faithfulness)
        self.relevance = float(relevance)
        self.completeness = float(completeness)
        self.passed = bool(passed)
        self.failure_type = failure_type
        self.context_precision = context_precision
        self.context_recall = context_recall

    def overall_score(self) -> float:
        """Compute the average of faithfulness, relevance, and completeness."""
        return (self.faithfulness + self.relevance + self.completeness) / 3.0


# ---------------------------------------------------------------------------
# Task 2 — RAGAS Evaluator (Simplified word-overlap heuristic)
# ---------------------------------------------------------------------------

STOPWORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "as", "by", "and", "or",
    "it", "its", "this", "that", "these", "those", "from", "into", "than",
}


def _tokenize(text: str | None) -> set[str]:
    """Lowercase word tokenization, ignoring punctuation and stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"\b\w+\b", str(text).lower())
    return {t for t in tokens if t not in STOPWORDS}


class RAGASEvaluator:
    """
    Evaluates RAG pipeline outputs using RAGAS-inspired heuristics.
    """

    def evaluate_faithfulness(self, answer: str, context: str) -> float:
        answer_tokens = _tokenize(answer)
        if not answer_tokens:
            return 1.0
        context_tokens = _tokenize(context)
        overlap = len(answer_tokens & context_tokens)
        score = overlap / len(answer_tokens)
        return max(0.0, min(1.0, score))

    def evaluate_relevance(self, answer: str, question: str) -> float:
        question_tokens = _tokenize(question)
        if not question_tokens:
            return 1.0
        answer_tokens = _tokenize(answer)
        overlap = len(answer_tokens & question_tokens)
        score = overlap / len(question_tokens)
        return max(0.0, min(1.0, score))

    def evaluate_completeness(self, answer: str, expected: str) -> float:
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        answer_tokens = _tokenize(answer)
        overlap = len(answer_tokens & expected_tokens)
        score = overlap / len(expected_tokens)
        return max(0.0, min(1.0, score))

    def evaluate_context_recall(self, contexts: list[str], expected: str) -> float:
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        if not contexts:
            return 0.0

        union_tokens: set[str] = set()
        for chunk in contexts:
            union_tokens.update(_tokenize(chunk))

        overlap = len(expected_tokens & union_tokens)
        score = overlap / len(expected_tokens)
        return max(0.0, min(1.0, score))

    def evaluate_context_precision(
        self,
        contexts: list[str],
        expected: str,
        relevance_threshold: float = 0.1,
    ) -> float:
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        if not contexts:
            return 0.0

        relevant_flags: list[bool] = []
        for chunk in contexts:
            chunk_tokens = _tokenize(chunk)
            coverage = len(chunk_tokens & expected_tokens) / len(expected_tokens)
            relevant_flags.append(coverage >= relevance_threshold)

        total_relevant = sum(relevant_flags)
        if total_relevant == 0:
            return 0.0

        cum_relevant = 0
        sum_precisions = 0.0
        for k, is_rel in enumerate(relevant_flags, start=1):
            if is_rel:
                cum_relevant += 1
                precision_at_k = cum_relevant / k
                sum_precisions += precision_at_k

        score = sum_precisions / total_relevant
        return max(0.0, min(1.0, score))

    def run_full_eval(
        self,
        answer: str,
        question: str,
        context: str,
        expected: str,
        contexts: list[str] | None = None,
    ) -> EvalResult:
        faithfulness = self.evaluate_faithfulness(answer, context)
        relevance = self.evaluate_relevance(answer, question)
        completeness = self.evaluate_completeness(answer, expected)

        passed = bool(faithfulness >= 0.5 and relevance >= 0.5 and completeness >= 0.5)

        failure_type: str | None = None
        if not passed:
            if faithfulness < 0.3:
                failure_type = "hallucination"
            elif relevance < 0.3:
                failure_type = "irrelevant"
            elif completeness < 0.3:
                failure_type = "incomplete"
            else:
                failure_type = "off_topic"

        context_recall: float | None = None
        context_precision: float | None = None
        if contexts is not None:
            context_recall = self.evaluate_context_recall(contexts, expected)
            context_precision = self.evaluate_context_precision(contexts, expected)

        qa_pair = QAPair(
            question=question,
            expected_answer=expected,
            context=context,
            retrieved_contexts=contexts if contexts is not None else [],
        )

        return EvalResult(
            qa_pair=qa_pair,
            actual_answer=answer,
            faithfulness=faithfulness,
            relevance=relevance,
            completeness=completeness,
            passed=passed,
            failure_type=failure_type,
            context_precision=context_precision,
            context_recall=context_recall,
        )


def rerank_by_overlap(contexts: list[str], query: str) -> list[str]:
    """A minimal lexical reranker: sort chunks by word overlap with query."""
    query_tokens = _tokenize(query)
    return sorted(
        contexts,
        key=lambda c: len(_tokenize(c) & query_tokens),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Task 3 — LLM Judge
# ---------------------------------------------------------------------------

class LLMJudge:
    def __init__(self, judge_llm_fn: Callable[[str], str]) -> None:
        self.judge_llm_fn = judge_llm_fn

    def score_response(
        self,
        question: str,
        answer: str,
        rubric: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = (
            f"Question: {question}\n"
            f"Answer: {answer}\n"
            f"Rubric: {rubric}\n\n"
            "Score the response according to the rubric."
        )
        raw_response = self.judge_llm_fn(prompt)

        try:
            match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            parsed = json.loads(match.group(0)) if match else json.loads(raw_response)
            
            # Check whether parsed contains nested "scores" or flat criteria keys
            if "scores" in parsed and isinstance(parsed["scores"], dict):
                scores = {k: float(v) for k, v in parsed["scores"].items()}
                reasoning = parsed.get("reasoning", raw_response)
            else:
                scores = {}
                reasoning = parsed.get("reasoning", raw_response)
                for k in rubric:
                    if k in parsed:
                        scores[k] = float(parsed[k])
                    else:
                        scores[k] = 0.5
            return {"scores": scores, "reasoning": reasoning}
        except Exception:
            return {
                "scores": {k: 0.5 for k in rubric},
                "reasoning": raw_response,
            }

    def detect_bias(self, scores_batch: list[dict[str, Any]]) -> dict[str, Any]:
        if not scores_batch:
            return {
                "positional_bias": False,
                "leniency_bias": False,
                "severity_bias": False,
            }

        all_scores: list[float] = []
        for item in scores_batch:
            scores_dict = item.get("scores", {})
            for score in scores_dict.values():
                all_scores.append(float(score))

        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.5
        leniency_bias = avg_score > 0.8
        severity_bias = avg_score < 0.3

        positional_bias = False
        first_scores: list[float] = []
        later_scores: list[float] = []
        for item in scores_batch:
            vals = list(item.get("scores", {}).values())
            if len(vals) > 1:
                first_scores.append(vals[0])
                later_scores.extend(vals[1:])
        if first_scores and later_scores:
            avg_first = sum(first_scores) / len(first_scores)
            avg_later = sum(later_scores) / len(later_scores)
            if avg_first - avg_later >= 0.2:
                positional_bias = True

        return {
            "positional_bias": positional_bias,
            "leniency_bias": leniency_bias,
            "severity_bias": severity_bias,
        }


# ---------------------------------------------------------------------------
# Task 4 — Benchmark Runner
# ---------------------------------------------------------------------------

class BenchmarkRunner:
    def run(
        self,
        qa_pairs: list[QAPair],
        agent_fn: Callable[[str], str],
        evaluator: Any,
    ) -> list[EvalResult]:
        results: list[EvalResult] = []
        for pair in qa_pairs:
            actual_answer = agent_fn(pair.question)
            contexts = pair.retrieved_contexts if pair.retrieved_contexts else None
            res = evaluator.run_full_eval(
                answer=actual_answer,
                question=pair.question,
                context=pair.context,
                expected=pair.expected_answer,
                contexts=contexts,
            )
            res.qa_pair = pair
            results.append(res)
        return results

    def generate_report(self, results: list[EvalResult]) -> dict[str, Any]:
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "passed": 0,
                "pass_rate": 0.0,
                "avg_faithfulness": 0.0,
                "avg_relevance": 0.0,
                "avg_completeness": 0.0,
                "avg_context_recall": None,
                "avg_context_precision": None,
                "failure_types": {},
            }

        passed_count = sum(1 for r in results if r.passed)
        avg_faithfulness = sum(r.faithfulness for r in results) / total
        avg_relevance = sum(r.relevance for r in results) / total
        avg_completeness = sum(r.completeness for r in results) / total

        recalls = [r.context_recall for r in results if r.context_recall is not None]
        avg_context_recall = (sum(recalls) / len(recalls)) if recalls else None

        precisions = [r.context_precision for r in results if r.context_precision is not None]
        avg_context_precision = (sum(precisions) / len(precisions)) if precisions else None

        failure_types: dict[str, int] = {}
        for r in results:
            if not r.passed and r.failure_type:
                failure_types[r.failure_type] = failure_types.get(r.failure_type, 0) + 1

        return {
            "total": total,
            "passed": passed_count,
            "pass_rate": passed_count / total,
            "avg_faithfulness": avg_faithfulness,
            "avg_relevance": avg_relevance,
            "avg_completeness": avg_completeness,
            "avg_context_recall": avg_context_recall,
            "avg_context_precision": avg_context_precision,
            "failure_types": failure_types,
        }

    def run_regression(self, new_results: list[EvalResult], baseline_results: list[EvalResult]) -> dict[str, Any]:
        def calc_avg(res: list[EvalResult]):
            if not res:
                return 0.0, 0.0, 0.0
            n = len(res)
            return (
                sum(r.faithfulness for r in res) / n,
                sum(r.relevance for r in res) / n,
                sum(r.completeness for r in res) / n,
            )

        new_f, new_r, new_c = calc_avg(new_results)
        base_f, base_r, base_c = calc_avg(baseline_results)

        regressions: list[str] = []
        if (base_f - new_f) > 0.05:
            regressions.append("faithfulness")
        if (base_r - new_r) > 0.05:
            regressions.append("relevance")
        if (base_c - new_c) > 0.05:
            regressions.append("completeness")

        return {
            "new_avg_faithfulness": new_f,
            "new_avg_relevance": new_r,
            "new_avg_completeness": new_c,
            "baseline_avg_faithfulness": base_f,
            "baseline_avg_relevance": base_r,
            "baseline_avg_completeness": base_c,
            "regressions": regressions,
            "passed": len(regressions) == 0,
        }

    def identify_failures(
        self,
        results: list[EvalResult],
        threshold: float = 0.5,
    ) -> list[EvalResult]:
        failures = []
        for r in results:
            if (
                r.faithfulness < threshold
                or r.relevance < threshold
                or r.completeness < threshold
            ):
                failures.append(r)
        return failures


# ---------------------------------------------------------------------------
# Task 5 — Failure Analyzer
# ---------------------------------------------------------------------------

class FailureAnalyzer:
    def categorize_failures(
        self, failures: list[EvalResult]
    ) -> dict[str, int]:
        categories: dict[str, int] = {}
        for f in failures:
            ft = f.failure_type or "unknown"
            categories[ft] = categories.get(ft, 0) + 1
        return categories

    def find_root_cause(self, failure: EvalResult) -> str:
        scores = {
            "faithfulness": failure.faithfulness,
            "relevance": failure.relevance,
            "completeness": failure.completeness,
        }
        min_metric = min(scores, key=lambda k: scores[k])
        lowest_score = scores[min_metric]

        ties = [k for k, v in scores.items() if abs(v - lowest_score) < 1e-6 and v < 0.5]
        if len(ties) > 1:
            return "Multiple issues detected — review full pipeline"

        if min_metric == "faithfulness":
            return "Context is missing or irrelevant — improve retrieval"
        elif min_metric == "relevance":
            return "Answer does not address the question — improve prompt clarity"
        else:
            return "Answer is missing key information — increase context window or improve generation"

    def generate_improvement_log(self, failures: list[EvalResult], suggestions: list[str]) -> str:
        lines = [
            "| Failure ID | Type | Root Cause | Suggested Fix | Status |",
            "|------------|------|------------|---------------|--------|",
        ]
        for i, failure in enumerate(failures):
            fid = f"F{i+1:03d}"
            ftype = failure.failure_type or "Unknown"
            rc = self.find_root_cause(failure)
            sugg = suggestions[i] if i < len(suggestions) else (suggestions[0] if suggestions else "Review pipeline")
            lines.append(f"| {fid} | {ftype} | {rc} | {sugg} | Open |")
        return "\n".join(lines)

    def generate_improvement_suggestions(
        self, failures: list[EvalResult]
    ) -> list[str]:
        if not failures:
            return []

        counts = self.categorize_failures(failures)
        suggestions: list[str] = []

        if counts.get("hallucination", 0) > 0 or counts.get("Hallucination", 0) > 0:
            suggestions.append("Implement hallucination checker to filter unsupported claims")
        if counts.get("incomplete", 0) > 0 or counts.get("Low_completeness", 0) > 0:
            suggestions.append("Increase chunk size in RAG pipeline to reduce context fragmentation")
        if counts.get("irrelevant", 0) > 0:
            suggestions.append("Refine system prompts and add few-shot examples to improve relevance")
        if counts.get("off_topic", 0) > 0:
            suggestions.append("Improve intent detection and query routing before retrieval")

        default_pool = [
            "Increase chunk size in RAG pipeline to reduce context fragmentation",
            "Add few-shot examples showing complete answers to improve completeness",
            "Implement hallucination checker to filter unsupported claims",
        ]
        for s in default_pool:
            if s not in suggestions and len(suggestions) < 3:
                suggestions.append(s)

        return suggestions