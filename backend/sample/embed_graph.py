import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_neo4j import Neo4jVector

from config.main import settings
from sample.system_check import DeviceManager

device_manager = DeviceManager()

# Single source of truth for the embedding side of the knowledge graph. Anything
# that queries the `ESSA` index has to embed with the same model, or Neo4j
# rejects the query on a vector-dimension mismatch.
#For mlx...
#| LLM inference | MLX (`Qwen/Qwen3-4B-MLX-4bit`) — Apple Silicon only |
#| Embeddings | `sentence-transformers/all-MiniLM-L12-v2` via HuggingFace |


EMBEDDING_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
EMBEDDING_DIMENSION = 1024
VECTOR_INDEX_NAME = "ESSA"

# The model's own default is 32768 tokens, and the longest bill node is ~29k
# characters — a full-length batch at that window will not fit in 16 GB of VRAM.
# 2048 tokens leaves >99% of nodes untruncated.
MAX_SEQ_LENGTH = 2048
ENCODE_BATCH_SIZE = 16

# FlashAttention-2, as the Qwen3-Embedding model card specifies. There is no
# `flash-attn` wheel for torch 2.13 and no nvcc here to build one, so this
# resolves to the prebuilt Hub kernel `kernels-community/flash-attn2` instead —
# which needs transformers >= 5.17 (earlier versions pin that kernel to v1,
# whose builds stop at torch 2.12, and fail with a misleading "the package for
# FlashAttention2 doesn't seem to be installed") and the `kernels` package.
# FA2 is CUDA-only, so non-NVIDIA devices fall back to torch's own fused
# attention rather than failing to load.
ATTENTION_IMPLEMENTATION = "flash_attention_2" if device_manager.is_nvidia() else "sdpa"

# Qwen3-Embedding pools on the last token (`1_Pooling/config.json` sets
# `pooling_mode_lasttoken`), and its model card asks for left padding.
PADDING_SIDE = "left"


class VectorStore:
    def __init__(self):
        """Hold the embedding model and the Neo4j-backed vector store.

        Parameters:
            None.

        Returns:
            None.

        Loads the embedding model eagerly — it is the expensive part and every
        method here needs it — and leaves `vector_store` unset until
        `set_vector_store` is called, so callers that only want to embed text
        do not pay for a database round trip.

        """

        self.embedding_model = self.set_embedding_model()
        self.vector_store = None

    def set_embedding_model(self):
        """Build the sentence-transformers embedding model for this machine.

        Parameters:
            None.

        Returns:
            HuggingFaceEmbeddings: The embedding model, already on the local
                accelerator.

        Resolves the torch device through `DeviceManager` (cuda, mps, or cpu)
        rather than branching on a specific vendor, so the same code path works
        on every box. `attn_implementation` and `dtype` are nested inside
        `model_kwargs` because langchain forwards the outer dict to
        `SentenceTransformer.__init__`, which takes its own `model_kwargs` for
        the underlying transformers model; `processor_kwargs` sits in the outer
        dict because left padding is a tokenizer setting, not a model one.
        `multi_process` stays off: that path in langchain calls
        `encode_multi_process`, which silently discards `encode_kwargs` and
        `query_encode_kwargs`.

        """

        embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            multi_process=False,
            model_kwargs={
                "device": device_manager.device,
                "model_kwargs": {
                    "attn_implementation": ATTENTION_IMPLEMENTATION,
                    "dtype": "bfloat16",
                },
                # The model card calls this `tokenizer_kwargs`; sentence-transformers 6
                # renamed it to `processor_kwargs` and only warns on the old name.
                "processor_kwargs": {"padding_side": PADDING_SIDE},
            },
            encode_kwargs={
                "normalize_embeddings": True,  # Set `True` for cosine similarity
                "batch_size": ENCODE_BATCH_SIZE,
                "convert_to_numpy": True,
            },
            # Qwen3-Embedding is asymmetric: queries carry the instruction
            # prompt shipped in the model's own config, documents do not.
            query_encode_kwargs={
                "normalize_embeddings": True,
                "convert_to_numpy": True,
                "prompt_name": "query",
            },
        )

        embedding_model._client.max_seq_length = MAX_SEQ_LENGTH

        return embedding_model

    def get_vector_store(self):
        """Return the vector store built by `set_vector_store`.

        Parameters:
            None.

        Returns:
            Neo4jVector | None: The vector store, or None if
                `set_vector_store` has not run yet.

        Hands back the cached instance without touching the database.

        """

        return self.vector_store

    def set_vector_store(self):
        """Embed every `Embeddable` node and attach the Neo4j vector index.

        Parameters:
            None.

        Returns:
            Neo4jVector: The vector store backing the `ESSA` index.

        Points `Neo4jVector.from_existing_graph` at the nodes labelled
        `Embeddable`, which creates the vector index if it is missing, then
        embeds each node's `text` and `type` properties and writes the result
        to the `embedding` property. `retrieval_query` widens a hit at query
        time to include its siblings in the bill hierarchy, so a matched clause
        is returned with the surrounding context rather than on its own.

        """

        retrieval_query = """  
            WITH node AS doc, score AS similarity
            ORDER BY similarity DESC LIMIT 4
            OPTIONAL MATCH (doc) - [:part_of]-> (parent) <- [:part_of] - (siblings)
            WITH doc.text AS self, reduce(s="", text in collect(siblings.text) | s + "\n" + text) AS contextText, similarity, {} AS metadata
        
            RETURN self + contextText AS text, similarity AS score, {} as metadata 
        
            """

        self.vector_store = Neo4jVector.from_existing_graph(
            embedding=self.embedding_model,
            url=settings.NEO4J_URL,
            username=settings.NEO4J_USERNAME,
            password=settings.NEO4J_PW,
            database=settings.NEO4J_DB,
            index_name=VECTOR_INDEX_NAME,
            node_label="Embeddable",
            embedding_node_property="embedding",
            text_node_properties=["text", "type"],
            retrieval_query=retrieval_query,
        )

        return self.vector_store
