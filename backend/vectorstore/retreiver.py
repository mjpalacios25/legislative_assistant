import re
from typing import List, Tuple

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_neo4j import Neo4jVector
from langchain_core.documents import Document
from langchain.messages import HumanMessage, SystemMessage

from config.main import settings

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L12-v2"

embedding_model = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL_NAME,
    multi_process=False,
    model_kwargs={"device": "mps"},
    encode_kwargs={"normalize_embeddings": True, "convert_to_numpy": True},
)

retrieval_query = """
    WITH node AS doc, score AS similarity
    ORDER BY similarity DESC LIMIT 4
    OPTIONAL MATCH (doc) - [:part_of]-> (parent) <- [:part_of] - (siblings)
    WITH doc.text AS self, reduce(s="", text in collect(siblings.text) | s + "\n" + text) AS contextText, similarity, {} AS metadata

    RETURN self + contextText AS text, similarity AS score, {} as metadata
    """

vector_store = Neo4jVector.from_existing_index(
    embedding=embedding_model,
    url=settings.NEO4J_URL,
    username=settings.NEO4J_USERNAME,
    password=settings.NEO4J_PW,
    database=settings.NEO4J_DB,
    index_name="ESSA",
    retrieval_query=retrieval_query,
)

user_input = """Context:
{context}
---
Now here is the question you need to answer.

Question: {question}"""


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        block if isinstance(block, str) else block.get("text", "")
        for block in content
    )


async def build_rag_messages(
    question: str,
    knowledge_index: Neo4jVector,
    num_retrieved_docs: int = 4,
    num_docs_final: int = 1,
) -> List:
    """Retrieve docs and build RAG prompt messages (no LLM call)."""
    print("=> Retrieving documents...")
    relevant_docs = knowledge_index.similarity_search(query=question, k=num_retrieved_docs)
    relevant_docs = [doc.page_content for doc in relevant_docs][:num_docs_final]

    context = "\nExtracted documents:\n"
    context += "".join(
        [f"Document {str(i)}:::\n" + doc for i, doc in enumerate(relevant_docs)]
    )

    final_prompt = user_input.format(question=question, context=context)
    print("==> final prompt: ", final_prompt)

    return [
        SystemMessage(
            "you are a legislative aide responsible for conducting policy research, summarizing legislation, and drafting new legislative text. Generate response with 100 percent fidelity to the provided context. Cite the sources that you use in your responses."
        ),
        HumanMessage(final_prompt),
    ]


async def answer_with_rag(
    question: str,
    llm,
    knowledge_index: Neo4jVector,
    num_retrieved_docs: int = 4,
    num_docs_final: int = 1,
) -> Tuple[str, List[Document]]:
    """Retrieve docs, invoke LLM, return (clean_answer_text, source_docs)."""
    print("=> Retrieving documents...")
    relevant_docs = knowledge_index.similarity_search(query=question, k=num_retrieved_docs)
    relevant_docs_text = [doc.page_content for doc in relevant_docs][:num_docs_final]

    context = "\nExtracted documents:\n"
    context += "".join(
        [f"Document {str(i)}:::\n" + doc for i, doc in enumerate(relevant_docs_text)]
    )

    final_prompt = user_input.format(question=question, context=context)

    local_messages = [
        SystemMessage(
            "you are a legislative aide responsible for conducting policy research, summarizing legislation, and drafting new legislative text. Generate response with 100 percent fidelity to the provided context. Cite the sources that you use in your responses."
        ),
        HumanMessage(final_prompt),
    ]

    print("=> Generating answer...")
    response = llm.invoke(local_messages)

    raw_content = _extract_text(response.content)
    clean_content = re.sub(r"<think>.*?</think>\s*", "", raw_content, flags=re.DOTALL)
    print("=> answer without thinking block", clean_content)

    return clean_content, relevant_docs


if __name__ == "__main__":
    import asyncio
    from llm.model import chat_model

    asyncio.run(
        answer_with_rag(
            question="what is title I about?",
            llm=chat_model,
            knowledge_index=vector_store,
        )
    )
