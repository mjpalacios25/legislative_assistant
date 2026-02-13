from langchain_huggingface import HuggingFaceEmbeddings
from langchain_neo4j import Neo4jVector
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX
from langchain_core.documents import Document
from langchain.messages import HumanMessage, SystemMessage, AIMessage
from typing import Optional, Tuple, List

from multiprocessing import Process, freeze_support, set_start_method
import sys
import os
import re

from config.main import settings

# --- Monkey-patch MLXPipeline._call to fix formatter incompatibility ---
# langchain-community 0.4.1 passes `formatter` to mlx_lm.generate(),
# but mlx-lm 0.28.3 forwards **kwargs to generate_step() which doesn't
# accept it. Strip `formatter` before calling generate().
_original_call = MLXPipeline._call

def _patched_call(self, prompt, stop=None, run_manager=None, **kwargs):
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_logits_processors, make_sampler

    pipeline_kwargs = kwargs.get("pipeline_kwargs", self.pipeline_kwargs) or {}

    temp = pipeline_kwargs.get("temp", 0.0)
    max_tokens = pipeline_kwargs.get("max_tokens", 100)
    verbose = pipeline_kwargs.get("verbose", False)
    repetition_penalty = pipeline_kwargs.get("repetition_penalty", None)
    repetition_context_size = pipeline_kwargs.get("repetition_context_size", None)
    top_p = pipeline_kwargs.get("top_p", 1.0)
    min_p = pipeline_kwargs.get("min_p", 0.0)
    min_tokens_to_keep = pipeline_kwargs.get("min_tokens_to_keep", 1)

    sampler = make_sampler(temp, top_p, min_p, min_tokens_to_keep)
    logits_processors = make_logits_processors(
        None, repetition_penalty, repetition_context_size
    )

    return generate(
        model=self.model,
        tokenizer=self.tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        verbose=verbose,
        sampler=sampler,
        logits_processors=logits_processors,
    )

MLXPipeline._call = _patched_call

def _patched_stream(self, prompt, stop=None, run_manager=None, **kwargs):
    import mlx.core as mx
    from mlx_lm.generate import generate_step  # fixed: was mlx_lm.utils
    from mlx_lm.sample_utils import make_logits_processors, make_sampler
    from langchain_core.outputs import GenerationChunk

    pipeline_kwargs = kwargs.get("pipeline_kwargs", self.pipeline_kwargs) or {}

    temp = pipeline_kwargs.get("temp", 0.0)
    max_new_tokens = pipeline_kwargs.get("max_tokens", 100)
    repetition_penalty = pipeline_kwargs.get("repetition_penalty", None)
    repetition_context_size = pipeline_kwargs.get("repetition_context_size", None)
    top_p = pipeline_kwargs.get("top_p", 1.0)
    min_p = pipeline_kwargs.get("min_p", 0.0)
    min_tokens_to_keep = pipeline_kwargs.get("min_tokens_to_keep", 1)

    prompt = self.tokenizer.encode(prompt, return_tensors="np")
    prompt_tokens = mx.array(prompt[0])

    eos_token_id = self.tokenizer.eos_token_id
    detokenizer = self.tokenizer.detokenizer
    detokenizer.reset()

    sampler = make_sampler(temp or 0.0, top_p, min_p, min_tokens_to_keep)
    logits_processors = make_logits_processors(
        None, repetition_penalty, repetition_context_size
    )

    for (token, prob), n in zip(
        generate_step(
            prompt=prompt_tokens,
            model=self.model,
            sampler=sampler,
            logits_processors=logits_processors,
        ),
        range(max_new_tokens),
    ):
        text = None
        detokenizer.add_token(token)
        detokenizer.finalize()
        text = detokenizer.last_segment

        if text:
            chunk = GenerationChunk(text=text)
            if run_manager:
                run_manager.on_llm_new_token(chunk.text)
            yield chunk

        if token == eos_token_id or (stop is not None and text in stop):
            break

MLXPipeline._stream = _patched_stream
# --- End monkey-patch ---

#Define the MLX LLM from Huggingface
llm = MLXPipeline.from_model_id(
    "Qwen/Qwen3-4B-MLX-4bit",
    pipeline_kwargs={"max_tokens": 4096, "temp": 0.1},
)

chat_model = ChatMLX(llm=llm)

#Define the embedding model from Huggingface
EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L12-v2'

embedding_model = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL_NAME,
    multi_process=True,
    model_kwargs={
        "device": "mps"
    },
    encode_kwargs={"normalize_embeddings": True, # Set `True` for cosine similarity
                "convert_to_numpy": True}
)

#Set up the NEO4j vector with a retreival query
retrieval_query = """  
    WITH node AS doc, score AS similarity
    ORDER BY similarity DESC LIMIT 4
    OPTIONAL MATCH (doc) - [:part_of]-> (parent) <- [:part_of] - (siblings)
    WITH doc.text AS self, reduce(s="", text in collect(siblings.text) | s + "\n" + text) AS contextText, similarity, {} AS metadata

    RETURN self + contextText AS text, similarity AS score, {} as metadata 

    """
vector_store = Neo4jVector.from_existing_index(
    embedding=embedding_model,
    url = settings.NEO4J_URL,
    username= settings.NEO4J_USERNAME,
    password= settings.db_password,
    database = settings.NEO4J_DB,
    index_name="ESSA",
    retrieval_query=retrieval_query
)

user_input = """Context:
{context}
---
Now here is the question you need to answer.

Question: {question}"""


async def build_rag_messages(
    question: str,
    knowledge_index: Neo4jVector,
    num_retrieved_docs: int = 4,
    num_docs_final: int = 1,
) -> List:
    """Retrieve docs and build RAG prompt messages (no LLM call)."""
    print("=> Retrieving documents...")
    relevant_docs = knowledge_index.similarity_search(
        query=question, k=num_retrieved_docs
    )
    relevant_docs = [doc.page_content for doc in relevant_docs][:num_docs_final]

    context = "\nExtracted documents:\n"
    context += "".join(
        [f"Document {str(i)}:::\n" + doc for i, doc in enumerate(relevant_docs)]
    )

    final_prompt = user_input.format(question=question, context=context)
    print("==> final prompt: ", final_prompt)

    return [
        SystemMessage("you are a legislative aide responsible for conducting policy research, summarizing legislation, and drafting new legislative text. Generate response with 100 percent fidelity to the provided context. Cite the sources that you use in your responses."),
        HumanMessage(final_prompt),
    ]


#define functions that retrieves docs from NEO4j and produces a final response.
async def answer_with_rag(
    question: str,
    llm: ChatMLX,
    knowledge_index: Neo4jVector,
    num_retrieved_docs: int = 4,
    num_docs_final: int = 1,
) -> Tuple[str, List[Document]]:
    # Gather documents with retriever

    print("=> Retrieving documents...")
    relevant_docs = knowledge_index.similarity_search(
        query=question, k=num_retrieved_docs
    )
    relevant_docs = [doc.page_content for doc in relevant_docs]  # Keep only the text

    relevant_docs = relevant_docs[:num_docs_final]

    # Build the final prompt
    context = "\nExtracted documents:\n"
    context += "".join(
        [f"Document {str(i)}:::\n" + doc for i, doc in enumerate(relevant_docs)]
    )

    final_prompt = user_input.format(question=question, context=context)

    local_messages = [
        SystemMessage("""you are a legislative aide responsible for conducting policy research, summarizing legislation, and drafting new legislative text. Generate response with 100 percent fidelity to the provided context. Cite the sources that you use in your responses."""),
        HumanMessage(final_prompt)
    ]

    # Redact an answer
    print("=> Generating answer...")

    response = llm.invoke(local_messages)
    print("=> LLM response:", response.content)

    # Strip thinking block from response
    response.content = re.sub(r"<think>.*?</think>\s*", "", response.content, flags=re.DOTALL)

    print("=> answer without thinking block", response.content)

    # sampler = make_sampler(temp=0)

    # response = generate(
    #     model=llm,
    #     # tokenizer=tokenizer,
    #     prompt=final_prompt,
    #     sampler=sampler,
    #     max_tokens=4000,
    #     verbose=True
    # )

    return response, relevant_docs

if __name__ == "__main__":
    answer_with_rag(
            question="what is title I about?",
            llm=chat_model,
            knowledge_index=vector_store
        )
