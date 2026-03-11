

from pydantic import BaseModel
from dataclasses import dataclass
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluationResult
from pydantic_evals import Dataset
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX
from langchain_neo4j import Neo4jVector
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from generate_dataset import Chunk, ChunkEval
from typing import Literal, Optional
from vectorstore.retreiver import answer_with_rag, vector_store
from config.main import PUBLIC_DIR
import logfire
import concurrent.futures
import tabulate


# llm = MLXPipeline.from_model_id(
#     "Qwen/Qwen3-4B-MLX-4bit",
#     pipeline_kwargs={"max_tokens": 4096, "temp": 0.1},
# )

# chat_model = ChatMLX(llm=llm)

#Create functions to calculate MRR and Recall

def calculate_mrr(predictions: list[str], gt: list[str]):
    mrr = 0
    for label in gt:
        if label in predictions:
            # Find the relevant item that has the smallest index
            mrr = max(mrr, 1 / (predictions.index(label) + 1))
    return mrr


def calculate_recall(predictions: list[str], gt: list[str]):
    # Calculate the proportion of relevant items that were retrieved
    return len([label for label in gt if label in predictions]) / len(gt)

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
        max_k = 25
    ):
    docs = knowledgeGraph.similarity_search_with_score(query=question, k=max_k)

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
    max_k=25,
):
    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(
        pool,
        partial(retrieve, knowledgeGraph, question, max_k),
    )
    return [item["doc"] for item in resp]

#function to visualize the results
def visualise_scores(result: EvaluationResult):
    scores = result.averages().scores
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
    logfire.configure()

    evaluation_queries = Dataset.from_file(PUBLIC_DIR / "questions.yaml")
    evaluation_queries.add_evaluator(RagMetricsEvaluator())

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        result = await evaluation_queries.evaluate(
            partial(retrieve_results, knowledgeGraph=vector_store, pool=executor)
        )

    visualise_scores(result)
    return result

if __name__ == "__main__":
    asyncio.run(main())