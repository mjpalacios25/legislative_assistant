from bs4 import BeautifulSoup, Tag, NavigableString
import pandas as pd
from typing import List, Dict
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from sample.utils import BillParser, delete_duplicate_edges
from config.main import PUBLIC_DIR, PARSER_DIR

# # Knowledge Graph Implementation

## Build knowledge graph by extracting text from XML using Beautiful Soup then splitting legislative text into
## its various components, then saving into .tsv format expected by Neo4j
with open(PUBLIC_DIR / "BILLS-114s1177enr.xml") as bill_xml:
    soup = BeautifulSoup(bill_xml, "xml")


#create file for nodes and one |for edges

node_columns = ["id", "number", "label", "type", "quoted", "text"]
edge_columns = ["source_id", "target_id", "type"]

nodes: pd.DataFrame = pd.DataFrame(columns= node_columns)
edges: pd.DataFrame = pd.DataFrame(columns= edge_columns)


#parse the bill and save nodes and edges as distinct variables
parser = BillParser(
    xml_soup = soup,
    node_columns= node_columns,
    edge_columns= edge_columns
)

parser.parse("HBCB1043F254B467C880CA4632EB8661D")

nodes_temp = parser.nodes_temp
edges_temp = parser.edges_temp


# convert nodes and edges to pandas dataframe
nodes = pd.DataFrame(nodes_temp)
edges = pd.DataFrame(edges_temp)

#remove duplicate edges
edges = delete_duplicate_edges(edges)

# save file for each type of node 

node_types = nodes["type"].unique().tolist()

#create directories to save files

os.makedirs(PARSER_DIR / "nodes", exist_ok=True)
os.makedirs(PARSER_DIR / "relationships", exist_ok=True)

#create separate files for each node type
for node_type in node_types:
    #filters by node type 
    type_node = nodes[nodes["type"] == node_type]

    #create file for this node type
    filename = f"{PARSER_DIR}/nodes/{node_type}_nodes.tsv"

    #make copy of node file
    export_df = type_node.copy()

    #rename id column to ":ID"
    headers = export_df.columns.tolist()
    headers[headers.index("id")] = ":ID"

    #add :LABEL column with the node type
    export_df[":LABEL"] = node_type.capitalize()
    headers.append(":LABEL")

    #export to .tsv
    export_df.to_csv(
        filename,
        sep = "\t",
        index = False,
        header = headers,
        escapechar = "\\",
        quoting = 3, 
        na_rep = "",
    )


#create separate files for each edge type

edge_types = edges["type"].unique().tolist()

for edge_type in edge_types:
    #filter out 

    type_edge = edges[edges["type"] == edge_type].copy()

    #create file for this edge
    filename = f"{PARSER_DIR}/relationships/{edge_type}_relationships.tsv"

    #rename columns for neo4j
    type_edge.rename(
        columns = {
            "source_id": ":START_ID",
            "target_id": ":END_ID",
            "type": "TYPE"
        },
        inplace = True
    )
    #export to tsv
    type_edge.to_csv(
        filename,
        sep = "\t",
        index = False,
        escapechar = "\\",
        quoting = 3, 
        na_rep = "",
    )

    






