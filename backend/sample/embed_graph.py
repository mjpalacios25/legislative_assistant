from langchain_huggingface import HuggingFaceEmbeddings
from langchain_neo4j import Neo4jVector

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.main import settings

#integrate embeddings into the knowledge graph and perform a sample similarity search on the graph

EMBEDDING_MODEL_NAME = 'sentence-transformers/all-MiniLM-L12-v2'
# EMBEDDING_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"


embedding_model = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL_NAME,
    # multi_process=True,
    model_kwargs={
        "device": "mps"
    },
    encode_kwargs={"normalize_embeddings": True, # Set `True` for cosine similarity
                "convert_to_numpy": True}
)



#should include here code to create the schema and create the graph.


# this snippet is only for the first time after creating knowledge graph so that we can add in embeddings. 
# add check to see if vectorstore already exists

retrieval_query = """  
WITH node AS doc, score AS similarity
ORDER BY similarity DESC LIMIT 4
OPTIONAL MATCH (doc) - [:part_of]-> (parent) <- [:part_of] - (siblings)
WITH doc.text AS self, reduce(s="", text in collect(siblings.text) | s + "\n" + text) AS contextText, similarity, {} AS metadata

RETURN self + contextText AS text, similarity AS score, {} as metadata 

"""

vector_store = Neo4jVector.from_existing_graph(
    embedding=embedding_model,
    url=settings.NEO4J_URL,
    username=settings.NEO4J_USERNAME,
    password=settings.NEO4J_PW,
    database=settings.NEO4J_DB,
    index_name="ESSA",
    node_label="Embeddable",
    embedding_node_property="embedding",
    text_node_properties=["text", "type"],
    retrieval_query=retrieval_query
)

# vector_store.query(
#     """MATCH (n) 
#     WHERE exists ((n) -[:part_of]->())
#     SET n:Embeddable """
# )



#since the vectorstore has already been created, use the "from existing index" method to initiatize the vector store

# vector_store = Neo4jVector.from_existing_index(
#     embedding=embedding_model,
#     url = settings.NEO4J_URL,
#     username= settings.NEO4J_USERNAME,
#     password= settings.NEO4J_PW,
#     database = settings.NEO4J_DB,
#     index_name="ESSA",
#     retrieval_query=retrieval_query
# )

question = "how much money does the bill appropriate for state assessments?" #this is where the text send by the client is passed to the knowledge graph to retreive relevant docs

response = vector_store.similarity_search(question, k=1)

for doc in response:
    print("document: ", doc)
