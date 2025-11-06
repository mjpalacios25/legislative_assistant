
# %% [markdown]
# # Knowledge Graph Implementation

# %%
## Build knowledge graph by extracting text from XML using Beautiful Soup then splitting legislative text into
## its various components, then saving into .tsv format expected by Neo4j

#load ESSA bill using beautiful soup
from bs4 import BeautifulSoup, Tag, NavigableString
import pandas as pd
from typing import List, Dict
import os

with open("public/BILLS-114s1177enr.xml") as bill_xml:
    soup = BeautifulSoup(bill_xml, "xml")


#create file for nodes and one |for edges

node_columns = ["id", "number", "label", "type", "quoted", "text"]
edge_columns = ["source_id", "target_id", "type"]

nodes: pd.DataFrame = pd.DataFrame(columns= node_columns)
edges: pd.DataFrame = pd.DataFrame(columns= edge_columns)

nodes_temp: List[Dict] = []
edges_temp: List[Dict] = []




# %%
quotedblock = soup.bill.find(id = "HD3D7D15B682F4D3D8A4A266F7B84B3C3")

print(quotedblock.parent.name)


# %%
#functions to parse xml content and each type of component of the bill

def parse_content(xml_soup: BeautifulSoup):

    leg = xml_soup.bill

    parse_bill()



    ##parse titles
    for titles in leg.find_all(id = "HBCB1043F254B467C880CA4632EB8661D"): #for production, go with find_all("title", id = True)

        parse_title(titles)

        # parse parts. need to add condition for parts nested inside of quoted tags
        for parts in titles.find_all("part", id = True):
            
            parse_part(titles,parts)

            #parse sections.
            for section in parts.find_all("section"):

                parse_section(parts, section)
                
                #parse subsections. 
                for subsection in section.find_all("subsection"):

                    parse_subsection(section, subsection)

                    # parse paragraphs
                    for paragraph in subsection.find_all("paragraph"):

                        parse_paragraph(subsection, paragraph)


                        #parse subparagraphs

                        for subparagraph in paragraph.find_all("subparagraph"):

                            parse_subparagraph(paragraph, subparagraph)

                            #parse clauses and subclauses

                            for clause in subparagraph.find_all("clause"):

                                parse_clause(subparagraph, clause)

                                for subclause in clause.find_all("subclause"):
                                    
                                    parse_subclause(clause, subclause)

    


def parse_bill():

    node_data = {
        "id": "S1177",
        "number": "S1177",
        "label": "Every Student Succeeds Act",
        "type": "bill",
        "quoted": "false",
        "text": "Every Student Succeeds Act"
    }

    add_node(node_data)

def parse_title(title_element: Tag):
    number = title_element.enum.string
    text = title_element.header.string

    # test = element.enum.string
    # print(test)
    node_data = {
        "id": title_element["id"],
        "number": number,
        "label": text,
        "type": "title",
        "quoted": "false",
        "text": text
    }

    add_node(node_data)

    edge_data = {
        "source_id": title_element["id"],
        "target_id": "S1177",
        "type": "part_of",
        "context": "",
    }

    add_edge(edge_data)
    

def parse_part(title_element: Tag ,part_element: Tag):

    name = str(part_element.enum.string)
    header = str(part_element.header.string)

    quoted_block = False
    if part_element.parent.name == "quoted-block":
        quoted_block = True


    node_data = {
        "id": part_element["id"],
        "number": name,
        "label": f"{name} {header[:100]} ..."
        if len(header) > 100
        else f"{name} {header}",
        "type": "part",
        "quoted": quoted_block,
        "text": f"Part {name}: {header}"
    } 

    add_node(node_data)

    edge_data = {
        "source_id": part_element["id"],
        "target_id": title_element["id"]
        if quoted_block == False
        else part_element.parent.parent["id"],
        "type": "part_of",
        "context": "",
    }

    add_edge(edge_data)

def parse_section(part_element: Tag, section_element: Tag):
    name = str(section_element.enum.string)
    header = str(section_element.header.string)
    if section_element.find("text"):
        text = section_element.find("text")
        text = str(text.string)

    #need to add check on whether the section element is contained within a "quoted_block" element. If so, then this section is should include label "amendment"
    quoted_block = False
    if section_element.parent.name == "quoted-block":
        quoted_block = True
        #if quoted, the section should belong to the section it belongs to and not the part 

    node_data = {
        "id": section_element["id"],
        "number": name,
        "label": f"{name} {header[:100]}"
        if len(header) > 100
        else f"{name} {header[:100]}",
        "type": "section",
        "quoted": quoted_block,
        "text": f"SECTION {name} {header} {text}"
        if section_element["section-type"] == "section-one"
        else f"SEC. {name} {header} {text}"
    } 

    add_node(node_data)

    edge_data = {
        "source_id": section_element["id"],
        "target_id": part_element["id"]
        if quoted_block == False
        # else section_element.parent.parent["id"]
        else section_element.parent.parent["id"]
        ,
        "type": "part_of",
        "context": "",
    }

    add_edge(edge_data)

def parse_subsection(section_element: Tag, subsection_element: Tag):
    name = str(subsection_element.enum.string)
    if subsection_element.header:
        header = str(subsection_element.header.string) 
        header = header.replace("\n", "")

    if subsection_element.find("text"):
        # text = subsection_element.find("text")
        strings = [text.replace("\n", "") for text in subsection_element.stripped_strings]
        text = " ".join(strings)

    #have to include checks if parent is a quoted block. If so, change quoted property to true.
    quoted_block = False
    if section_element.parent.name == "quoted-block":
        quoted_block = True
        #if part of a quote block, this should only be connecting with the quoted section

    node_data = {
        "id": subsection_element["id"],
        "number": name,
        "label": f"{name} {header[:100]}"
        if len(header) > 100
        else f"{name} {header}",
        "type": "subsection",
        "quoted": quoted_block,
        "text": text
       
    } 

    add_node(node_data)

    edge_data = {
        "source_id": subsection_element["id"],
        "target_id": section_element["id"]
        if quoted_block == False
        else subsection_element.parent["id"], #maybe just a blank?
        "type": "part_of",
        "context": "",
    }

    add_edge(edge_data)

def parse_paragraph(subsection_element: Tag, paragraph_element: Tag):
    name = str(paragraph_element.enum.string)

    if paragraph_element.header:

        header = paragraph_element.header.string
    else:
        header = ""
    #debug to remove '\n' characters and make sure that 'None' is removed from generated text fields
    if paragraph_element.find("text"):
        text = paragraph_element.find("text")
        text = str(text.string)

    quoted_block = False
    if subsection_element.parent.parent.name == "quoted-block":
        quoted_block = True

    node_data = {
        "id": paragraph_element["id"],
        "number": name,
        "label": f"{name} {text[:100]} ... "
        if len(text) > 100
        else f"{name} {text}",
        "type": "paragraph",
        "quoted": quoted_block,
        "text": f"{name} {header} {text}"
       
    } 

    add_node(node_data)

    edge_data = {
        "source_id": paragraph_element["id"],
        "target_id": subsection_element["id"]
        if quoted_block == False
        else paragraph_element.parent["id"],
        "type": "part_of",
        "context": "",
    }

    add_edge(edge_data)
    


def parse_subparagraph(paragraph_element: Tag, subpara_element: Tag):
    name = str(subpara_element.enum.string)

    if subpara_element.header:

        header = subpara_element.header.string
    else:
        header = ""
    #debug to remove '\n' characters and make sure that 'None' is removed from generated text fields
    if subpara_element.find("text"):
        text = subpara_element.find("text")
        text = str(text.string)

    quoted_block = False
    if paragraph_element.parent.parent.parent.name == "quoted-block":
        quoted_block = True

    node_data = {
        "id": subpara_element["id"],
        "number": name,
        "label": f"{name} {text[:100]} ... "
        if len(text) > 100
        else f"{name} {text}",
        "type": "subparagraph",
        "quoted": quoted_block,
        "text": f"{name} {header} {text}"
       
    } 

    add_node(node_data)

    edge_data = {
        "source_id": subpara_element["id"],
        "target_id": paragraph_element["id"]
        if quoted_block == False
        else subpara_element.parent["id"],
        "type": "part_of",
        "context": "",
    }

    add_edge(edge_data)

def parse_clause(parent_element: Tag, child_element: Tag):
    name = str(child_element.enum.string)

    #debug to remove '\n' characters and make sure that 'None' is removed from generated text fields
    if child_element.find("text"):
        text = child_element.find("text")
        text = str(text.string)

    quoted_block = False
    if parent_element.parent.parent.parent.parent.name == "quoted-block":
        quoted_block = True

    node_data = {
        "id": child_element["id"],
        "number": name,
        "label": (text[:100] + "...")
        if len(text) > 100
        else text,
        "type": "clause",
        "quoted": quoted_block,
        "text": f"{name} {text}"
       
    } 

    add_node(node_data)

    edge_data = {
        "source_id": child_element["id"],
        "target_id": parent_element["id"]
        if quoted_block == False
        else child_element.parent["id"],
        "type": "part_of",
        "context": "",
    }

    add_edge(edge_data)

def parse_subclause(parent_element: Tag, child_element: Tag):
    name = str(child_element.enum.string)

    #debug to remove '\n' characters and make sure that 'None' is removed from generated text fields
    if child_element.find("text"):
        text = child_element.find("text")
        text = str(text.string)

    quoted_block = False
    if parent_element.parent.parent.parent.parent.parent.name == "quoted-block":
        quoted_block = True

    node_data = {
        "id": child_element["id"],
        "number": name,
        "label": (text[:100] + "...")
        if len(text) > 100
        else text,
        "type": "subclause",
        "quoted": quoted_block,
        "text": f"{name} {text}"
       
    } 

    add_node(node_data)

    edge_data = {
        "source_id": child_element["id"],
        "target_id": parent_element["id"]
        if quoted_block == False
        else child_element.parent["id"],
        "type": "part_of",
        "context": "",
    }

    add_edge(edge_data)

def clean_text(text):
    
    cleantext = text.replace("\n", "")

    return cleantext

# fundtions to add nodes and edges to graph

def add_node(node_data):
    "add a node to the node list"
    assert set(node_columns).issubset(
        node_data.keys()
    ), f"Missing node columns {node_columns}"

    nodes_temp.append(node_data)

def add_edge(edge_data):
    "add edge to the edge list"
    assert set(edge_columns).issubset(
        edges.keys()
    ), f"Missing edge columns {edge_columns}"

    edges_temp.append(edge_data)

def clear_temp_storage():
    node_temp = []
    edge_temp = []

def delete_duplicate_edges(edges: pd.DataFrame):

    edges = edges.drop_duplicates(
        subset=["source_id", "target_id", "type"]
    )
    return edges

def delete_quoted_edges(edges: pd.DataFrame):

    edges = edges.drop_duplicates(
        subset= ["source_id", "target_id", "type"], 
        keep="last"
    )

 
#parse the bill and save nodes and edges as distinct variables
parse_content(soup)


# %%
# convert nodes and edges to pandas dataframe
nodes = pd.DataFrame(nodes_temp)
edges = pd.DataFrame(edges_temp)

#remove duplicate edges
edges = delete_duplicate_edges(edges)

# save file for each type of node 

node_types = nodes["type"].unique().tolist()

#create directories to save files

os.makedirs("nodes", exist_ok=True)
os.makedirs("relationships", exist_ok=True)

#create separate files for each node type
for node_type in node_types:
    #filters by node type 
    type_node = nodes[nodes["type"] == node_type]

    #create file for this node type
    filename = f"{os.getcwd()}/nodes/{node_type}_nodes.tsv"

    #make copy of node file
    export_df = type_node.copy()

    #rename id columb to ":ID"
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
    filename = f"{os.getcwd()}/relationships/{edge_type}_relationships.tsv"

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

    






