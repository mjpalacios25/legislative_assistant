from neo4j import GraphDatabase
import csv
from collections import defaultdict
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.main import PARSER_DIR, settings
from sample.embed_graph import VectorStore

###  connect to neo4j and import the nodes and edges into the graph database


# Connection details come from .env via config.main.settings so the loader and
# the embedding step in sample/embed_graph.py always target the same database.
URI = settings.NEO4J_URL
AUTH = (settings.NEO4J_USERNAME, settings.NEO4J_PW)
DATABASE = settings.NEO4J_DB
BATCH_SIZE = 500

BILL_PATHS = f"{PARSER_DIR}/nodes"
RELATIONSHIP_PATH = f"{PARSER_DIR}/relationships"

DEFAULT_ID_COLUMN = ":ID"
DEFAULT_LABEL_COLUMN = ":LABEL"

NODE_FILES = [
    {
        "path": f"{BILL_PATHS}/bill_nodes.tsv",
        "label": "Bill",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    },
    {
        "path": f"{BILL_PATHS}/title_nodes.tsv",
        "label": "Title",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    },
    {
        "path": f"{BILL_PATHS}/part_nodes.tsv",
        "label": "Part",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    },
    {
        "path": f"{BILL_PATHS}/section_nodes.tsv",
        "label": "Section",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    },
    {
        "path": f"{BILL_PATHS}/subsection_nodes.tsv",
        "label": "Subsection",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    },
    {
        "path": f"{BILL_PATHS}/paragraph_nodes.tsv",
        "label": "Paragraph",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    },
    {
        "path": f"{BILL_PATHS}/subparagraph_nodes.tsv",
        "label": "Subparagraph",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    },
    {
        "path": f"{BILL_PATHS}/clause_nodes.tsv",
        "label": "Clause",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    },
    {
        "path": f"{BILL_PATHS}/subclause_nodes.tsv",
        "label": "Subclause",
        "id_column": ":ID",
        "prefix": None,
        "numeric_columns": [],      # e.g. ["age"]
        "list_columns": {},  
    }
]

REL_FILE = {
    "path": f"{RELATIONSHIP_PATH}/part_of_relationships.tsv",
    "source_column": ":START_ID",
    "target_column": ":END_ID",
    "source_prefix": None,
    "target_prefix": None,
    "type_column": "TYPE",
}

FIXED_REL_TYPE = None 
USE_LABEL_COLUMNS = True



 
def read_tsv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield row
 
 
def batched(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
 
 
def sanitize_label_or_type(name):
    """Keep only letters/digits/underscore — used for names we inline
    into the query string (labels, relationship types)."""
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in name.strip())
    return cleaned or "UNKNOWN"
 
 
def build_global_id(raw_id, prefix):
    return f"{prefix}:{raw_id}" if prefix else raw_id
 
 
def ensure_entity_constraint(driver):
    driver.execute_query(
        """
        CREATE CONSTRAINT entity_id IF NOT EXISTS
        FOR (e:Entity) REQUIRE e.id IS UNIQUE
        """,
        database_=DATABASE,
    )
 
 
def prepare_node_row(row, config):
    """Pull the id + label(s) out of the row, cast configured columns,
    and return (labels_tuple, cleaned_row)."""
    row = dict(row)
    id_column = config.get("id_column", DEFAULT_ID_COLUMN)
    label_column = config.get("label_column", DEFAULT_LABEL_COLUMN)
 
    raw_id = row.pop(id_column)
    row["id"] = build_global_id(raw_id, config.get("prefix"))
 
    raw_labels = row.pop(label_column, "") or ""
    labels = tuple(
        sanitize_label_or_type(part)
        for part in raw_labels.split(";")
        if part.strip()
    )
 
    for col in config.get("numeric_columns", []):
        if row.get(col) not in (None, ""):
            row[col] = float(row[col])
 
    for col, sep in config.get("list_columns", {}).items():
        if row.get(col):
            row[col] = row[col].split(sep)
 
    return labels, row
 
 
def import_node_file(driver, config):
    # Group by label(s) so each batch's SET clause can inline the
    # right label(s) — a node's type is read from its own row, but
    # rows sharing the same label(s) can still be batched together.
    grouped = defaultdict(list)
    for raw_row in read_tsv(config["path"]):
        labels, row = prepare_node_row(raw_row, config)
        if not labels:
            print(f"  skipping row with no label in {config['path']}: {row}")
            continue
        grouped[labels].append(row)
 
    total = 0
    for labels, rows in grouped.items():
        label_str = "".join(f":`{label}`" for label in labels)
        query = f"""
        UNWIND $rows AS row
        MERGE (n:Entity {{id: row.id}})
        SET n{label_str}
        SET n += row
        """
        for batch in batched(rows, BATCH_SIZE):
            driver.execute_query(query, rows=batch, database_=DATABASE)
            total += len(batch)
 
    seen_labels = sorted({labels[0] for labels in grouped})
    print(f"  {config['path']}: loaded {total} nodes ({', '.join(seen_labels)})")
 
 
def prepare_rel_row(row):
    row = dict(row)  # keep original columns available as properties too
 
    if USE_LABEL_COLUMNS:
        source_prefix = row.get("source_label")
        target_prefix = row.get("target_label")
    else:
        source_prefix = REL_FILE.get("source_prefix")
        target_prefix = REL_FILE.get("target_prefix")
 
    row["_source_id"] = build_global_id(row[REL_FILE["source_column"]], source_prefix)
    row["_target_id"] = build_global_id(row[REL_FILE["target_column"]], target_prefix)
    return row
 
 
def import_relationships(driver):
    rows = (prepare_rel_row(row) for row in read_tsv(REL_FILE["path"]))
 
    type_column = REL_FILE.get("type_column")
    grouped = defaultdict(list)
    for row in rows:
        rel_type = row[type_column] if type_column else FIXED_REL_TYPE
        grouped[rel_type].append(row)
 
    total = 0
    for rel_type, group_rows in grouped.items():
        safe_type = sanitize_label_or_type(rel_type)
        query = f"""
        UNWIND $rows AS row
        MATCH (s:Entity {{id: row._source_id}})
        MATCH (t:Entity {{id: row._target_id}})
        MERGE (s)-[r:`{safe_type}`]->(t)
        SET r += row
        """
        for batch in batched(group_rows, BATCH_SIZE):
            driver.execute_query(query, rows=batch, database_=DATABASE)
            total += len(batch)
        print(f"  {rel_type}: loaded relationships")
 
    print(f"  Total relationships loaded: {total}")

def add_embeddable_labels(driver):
    """Tag every node that sits inside the bill hierarchy as `Embeddable`.

    Parameters:
        driver (neo4j.Driver): An open driver for the target database.

    Returns:
        None.

    Marks the nodes the vector index should cover. A node earns the label by
    having an outgoing `part_of` relationship, which is true of every component
    of the bill and false for the bill node itself, so the root is left out of
    the index.

    """

    query = """
    MATCH (n)
    WHERE exists((n)-[:part_of]->())
    SET n:Embeddable
    """
    driver.execute_query(query, database_=DATABASE)


 
 
def main():
    """Load the parsed bill into Neo4j and embed it end to end.

    Parameters:
        None.

    Returns:
        None.

    Opens one driver for the whole run, creates the uniqueness constraint,
    imports every node file then the relationship file, labels the embeddable
    nodes, and hands off to `VectorStore` to write embeddings and create the
    vector index. Finishes by printing the node count as a sanity check that
    the import landed.

    """

    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        driver.verify_connectivity()
 
        print("Creating constraints...")
        ensure_entity_constraint(driver)
 
        print("Importing node files...")
        for config in NODE_FILES:
            import_node_file(driver, config)
 
        print("Importing relationships...")
        import_relationships(driver)

        print("Adding embeddable labels...")
        add_embeddable_labels(driver)

        print("Adding embeddings to nodes...")
        vector_store = VectorStore()
        vector_store.set_vector_store()
 
        records, _, _ = driver.execute_query(
            "MATCH (n:Entity) RETURN count(n) AS c", database_=DATABASE
        )
        print("Total node count:", records[0]["c"])
 
 
if __name__ == "__main__":
    main()