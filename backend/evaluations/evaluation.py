import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dataclasses import dataclass
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluationResult
from pydantic_evals import Dataset
from langchain_neo4j import Neo4jVector
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
# Embed queries with the exact model the index was built with -- Neo4j rejects
# a search whose vector dimension does not match the index. Importing from
# sample.embed_graph (not vectorstore.retreiver) avoids opening the chat
# endpoint's Neo4j store as an import side effect.
from sample.embed_graph import VectorStore, VECTOR_INDEX_NAME
from config.main import PUBLIC_DIR, settings
import logfire
import concurrent.futures
import tabulate


def _normalize(text: str) -> str:
    """Remove all whitespace and lowercase for robust comparison.

    The evaluation dataset (questions.yaml) was generated using BeautifulSoup's
    get_text() which concatenates XML text nodes with no separator, while the
    Neo4j nodes were ingested using stripped_strings + " ".join() which adds a
    space at every element boundary. Removing all whitespace before comparing
    makes the comparison robust to this difference.
    """
    return re.sub(r'\s+', '', text).lower()

#Create functions to calculate MRR and Recall

def calculate_mrr(predictions: list[str], gt: list[str]):
    norm_preds = [_normalize(p) for p in predictions]
    mrr = 0
    for label in gt:
        norm_label = _normalize(label)
        if norm_label in norm_preds:
            # Find the relevant item that has the smallest index
            mrr = max(mrr, 1 / (norm_preds.index(norm_label) + 1))
    return mrr


def calculate_recall(predictions: list[str], gt: list[str]):
    # Calculate the proportion of relevant items that were retrieved
    norm_preds = [_normalize(p) for p in predictions]
    return len([label for label in gt if _normalize(label) in norm_preds]) / len(gt)

def calculate_accuracy(predictions, gt):
    # Calculate the accuracy of the top result
    accuracy = predictions/gt
    return accuracy

# Define Our Metrics
metrics = [("recall", calculate_recall), ("mrr", calculate_mrr)]
k = [1, 3, 5, 10, 15, 20, 25, 30, 35, 40]

#define our retrieval function
def retrieve(
        knowledgeGraph: Neo4jVector,
        question: str,
        k= 40
    ):
    docs = knowledgeGraph.similarity_search_with_score(query=question, k=k)

    return [
        {"score": item[1], "doc": item[0].page_content} for item in docs
    ]



@dataclass
class RagMetricsEvaluator(Evaluator):
    async def evaluate(self, ctx: EvaluatorContext[str, str]) -> dict[str, float]:
        predictions = ctx.output
        labels = ctx.expected_output

        scores = {}

        for metric, score_fn in metrics:
            for subset_k in k:
                scores[f"{metric}@{subset_k}"] = score_fn(
                    predictions[:subset_k], labels
                )

        return scores

async def retrieve_results(
    question: str,
    knowledgeGraph: Neo4jVector,
    pool: ThreadPoolExecutor,
    k=40,
):
    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(
        pool,
        partial(retrieve, knowledgeGraph, question, k),
    )
    return [item["doc"] for item in resp]

#function to visualize the results
def visualise_scores(result: EvaluationResult):
    averages = result.averages()
    if averages is None:
        print("No evaluation scores — all cases may have failed.")
        return
    scores = averages.scores
    # Format the scores in a more readable way
    formatted_scores = {
        k: round(v, 2) if isinstance(v, float) else v for k, v in scores.items()
    }

    # Create a table with metrics as rows for better readability
    rows = []
    for k, v in formatted_scores.items():
        rows.append([k, v])

    print(tabulate.tabulate(rows, headers=["Metric", "Score"], tablefmt="grid"))


async def main():
    # Tracing is optional: export to Logfire only when LOGFIRE_TOKEN is set,
    # instead of raising LogfireConfigError on machines that never ran
    # `logfire auth`.
    logfire.configure(send_to_logfire="if-token-present")

    # Plain store — no retrieval_query so raw doc text is returned (exact match
    # to expected_output) and the k parameter is respected (no LIMIT override).

    retrieval_query = """  
    WITH node AS doc, score AS similarity
    ORDER BY similarity DESC LIMIT 40
    RETURN doc.text AS text, similarity AS score, {} as metadata

    """
    eval_vector_store = Neo4jVector.from_existing_index(
        embedding=VectorStore().embedding_model,
        url=settings.NEO4J_URL,
        username=settings.NEO4J_USERNAME,
        password=settings.NEO4J_PW,
        database=settings.NEO4J_DB,
        index_name=VECTOR_INDEX_NAME,
        retrieval_query=retrieval_query
    )

    evaluation_queries = Dataset.from_file(PUBLIC_DIR / "questions.yaml")
    evaluation_queries.add_evaluator(RagMetricsEvaluator())

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        result = await evaluation_queries.evaluate(
            partial(retrieve_results, knowledgeGraph=eval_vector_store, pool=executor)
        )

    visualise_scores(result)
    return result

if __name__ == "__main__":
    asyncio.run(main())