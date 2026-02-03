from transformers import pipeline
from mlx_lm import load, generate

model, tokenizer = load("Qwen/Qwen3-4B-MLX-4bit")



# %%
prompt_in_chat_format = [
    {
        "role": "system",
        "content": """you are a legislative aide responsible for conducting policy research, summarizing legislation, and drafting new legislative text. Generate response with 100 percent fidelity to the provided context. Cite the sources that you use in your responses.

        """,
    },
    {
        "role": "user",
        "content": """Context:
{context}
---
Now here is the question you need to answer.

Question: {question}""",
    },
]
RAG_PROMPT_TEMPLATE = tokenizer.apply_chat_template(
    prompt_in_chat_format, tokenize=False, add_generation_prompt=True
)
print(RAG_PROMPT_TEMPLATE)

# %%
import mlx
import mlx_lm
from mlx_lm.sample_utils import make_sampler

from typing import Optional, Tuple, List
from langchain.docstore.document import Document

def answer_with_rag(
    question: str,
    llm: mlx.nn.layers.base.Module,
    tokenizer: mlx_lm.tokenizer_utils.TokenizerWrapper,
    knowledge_index: Neo4jVector,
    # reranker: Optional[RAGPretrainedModel] = None,
    num_retrieved_docs: int = 4,
    num_docs_final: int = 1,
) -> Tuple[str, List[Document]]:
    # Gather documents with retriever

    print("=> Retrieving documents...")
    relevant_docs = knowledge_index.similarity_search(
        query=question, k=num_retrieved_docs
    )
    relevant_docs = [doc.page_content for doc in relevant_docs]  # Keep only the text

    # Optionally rerank results
    # if reranker:
    #     print("=> Reranking documents...")
    #     relevant_docs = reranker.rerank(question, relevant_docs, k=num_docs_final)
    #     relevant_docs = [doc["content"] for doc in relevant_docs]

    relevant_docs = relevant_docs[:num_docs_final]

    # Build the final prompt
    context = "\nExtracted documents:\n"
    context += "".join(
        [f"Document {str(i)}:::\n" + doc for i, doc in enumerate(relevant_docs)]
    )

    final_prompt = RAG_PROMPT_TEMPLATE.format(question=question, context=context)

    # Redact an answer
    print("=> Generating answer...")

    sampler = make_sampler(temp=0)

    response = generate(
        model=llm,
        tokenizer=tokenizer,
        prompt=final_prompt,
        sampler=sampler,
        max_tokens=4000,
        verbose=True
    )
    # answer = response[0]["generated_text"]

    return response, relevant_docs




# %%
full_response = answer_with_rag(question, model, tokenizer, vector_store )