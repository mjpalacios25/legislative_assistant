from langchain_huggingface import HuggingFaceEmbeddings
from multiprocessing import Process, freeze_support, set_start_method
from langchain_neo4j import Neo4jVector
import sys
import os

# Get the path to the current script's directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Get the path to the parent directory (one level up)
parent_dir = os.path.dirname(current_dir)

# Add the parent directory to sys.path
sys.path.append(parent_dir)
from backend.config.main import settings



if __name__ == '__main__':

    set_start_method('spawn')

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



    #should include here code to create the schema and create the graph.


    # this snippet is only for the first time after creating knowledge graph so that we can add in embeddings. 

    # vector_store = Neo4jVector.from_existing_graph(
    #     embedding=embedding_model,
    #     url = url,
    #     username=username,
    #     password=password,
    #     index_name="ESSA",
    #     node_label="Embeddable",
    #     embedding_node_property="embedding",
    #     text_node_properties=["text", "type"]
    # )




    #since the vectorstore has already been created, use the "from existing index" method to initiatize the vector store
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
        password= settings.NEO4J_PW,
        database = settings.NEO4J_DB,
        index_name="ESSA",
        retrieval_query=retrieval_query
    )

    question = "how much money does the bill appropriate for state assessments?" #this is where the text send by the client is passed to the knowledge graph to retreive relevant docs

    response = vector_store.similarity_search(question, k=1)


    for doc in response:
        print(doc)