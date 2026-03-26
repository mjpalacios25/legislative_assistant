from bs4 import BeautifulSoup, Tag, NavigableString
import pandas as pd
from typing import List, Dict
import unicodedata

#functions to parse xml content and each type of component of the bill

class BillParser:
    def __init__(self, xml_soup: BeautifulSoup, node_columns: pd.DataFrame, edge_columns: pd.DataFrame):
        self.xml_soup = xml_soup
        self.node_columns = node_columns
        self.edge_columns = edge_columns
        self.nodes_temp: List[Dict] = []
        self.edges_temp: List[Dict] = []

        
     # helper functions 

    def add_node(self, node_data: Dict):
        "add a node to the node list"
        assert set(self.node_columns).issubset(
            node_data.keys()
        ), f"Missing node columns {self.node_columns}"

        self.nodes_temp.append(node_data)

    def add_edge(self, edge_data: Dict):
        "add edge to the edge list"
        assert set(self.edge_columns).issubset(
            edge_data.keys()
        ), f"Missing edge columns {self.edge_columns}"

        self.edges_temp.append(edge_data)

    def clear_temp_storage(self):
        self.nodes_temp = []
        self.edges_temp = []

    @staticmethod
    def clean_text(element: Tag):
        if element is None:
            return ""
        text = ' '.join(element.get_text().split())
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        return text
    
    #kick off parsing
    
    def parse(self, id: str):

        self.parse_bill()

        leg = self.xml_soup.bill

        ##parse titles
        for titles in leg.find_all(id = id): #for production, go with find_all("title", id = True)

            self.parse_title(titles)

            # parse parts. need to add condition for parts nested inside of quoted tags
            for parts in titles.find_all("part", id = True):
                
                self.parse_part(titles,parts)

                #parse sections.
                for section in parts.find_all("section"):

                    self.parse_section(parts, section)
                    
                    #parse subsections. 
                    for subsection in section.find_all("subsection"):

                        self.parse_subsection(section, subsection)

                        # parse paragraphs
                        for paragraph in subsection.find_all("paragraph"):

                            self.parse_paragraph(subsection, paragraph)

                            #parse subparagraphs

                            for subparagraph in paragraph.find_all("subparagraph"):

                                self.parse_subparagraph(paragraph, subparagraph)

                                #parse clauses and subclauses

                                for clause in subparagraph.find_all("clause"):

                                    self.parse_clause(subparagraph, clause)

                                    for subclause in clause.find_all("subclause"):
                                        
                                        self.parse_subclause(clause, subclause)

    # parse functions

    def parse_bill(self):

        node_data = {
            "id": "S1177",
            "number": "S1177",
            "label": "Every Student Succeeds Act",
            "type": "bill",
            "quoted": "false",
            "text": "Every Student Succeeds Act"
        }

        self.add_node(node_data)

    def parse_title(self, title_element: Tag):
        number = self.clean_text(title_element.enum)
        text = self.clean_text(title_element.header)

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

        self.add_node(node_data)

        edge_data = {
            "source_id": title_element["id"],
            "target_id": "S1177",
            "type": "part_of",
            "context": "",
        }

        self.add_edge(edge_data)
        
    def parse_part(self, title_element: Tag ,part_element: Tag):

        name = self.clean_text(part_element.enum)
        header = self.clean_text(part_element.header)

        quoted_block = part_element.parent.name == "quoted-block"

        node_data = {
            "id": part_element["id"],
            "number": name,
            "label": f"{name} {header[:100]} ..." if len(header) > 100 else f"{name} {header}",
            "type": "part",
            "quoted": quoted_block,
            "text": f"Part {name}: {header}"
        } 

        self.add_node(node_data)

        edge_data = {
            "source_id": part_element["id"],
            "target_id": title_element["id"] if not quoted_block else part_element.parent.parent["id"],
            "type": "part_of",
            "context": "",
        }

        self.add_edge(edge_data)

    def parse_section(self, part_element: Tag, section_element: Tag):
        name = self.clean_text(section_element.enum)
        header = self.clean_text(section_element.header)
        text = self.clean_text(section_element.find("text")) if section_element.find("text") else ""

        #need to add check on whether the section element is contained within a "quoted_block" element. If so, then this section is should include label "amendment"
        quoted_block = section_element.parent.name == "quoted-block"
   
        #if quoted, the section should belong to the section it belongs to and not the part 

        node_data = {
            "id": section_element["id"],
            "number": name,
            "label": f"{name} {header[:100]}" if len(header) > 100 else f"{name} {header[:100]}",
            "type": "section",
            "quoted": quoted_block,
            "text": f"SECTION {name} {header} {text}" if section_element["section-type"] == "section-one" else f"SEC. {name} {header} {text}"
        } 

        self.add_node(node_data)

        edge_data = {
            "source_id": section_element["id"],
            "target_id": part_element["id"] if not quoted_block else section_element.parent.parent["id"]
            ,
            "type": "part_of",
            "context": "",
        }

        self.add_edge(edge_data)

    def parse_subsection(self, section_element: Tag, subsection_element: Tag):
        name = self.clean_text(subsection_element.enum) 
        header = self.clean_text(subsection_element.header) if subsection_element.header else ""
        text = self.clean_text(subsection_element) if subsection_element.find("text") else ""

        #have to include checks if parent is a quoted block. If so, change quoted property to true.
        quoted_block = section_element.parent.name == "quoted-block"
        
        #if part of a quote block, this should only be connecting with the quoted section

        node_data = {
            "id": subsection_element["id"],
            "number": name,
            "label": f"{name} {header[:100]}" if len(header) > 100 else f"{name} {header}",
            "type": "subsection",
            "quoted": quoted_block,
            "text": text
        
        } 

        self.add_node(node_data)

        edge_data = {
            "source_id": subsection_element["id"],
            "target_id": section_element["id"] if not quoted_block else subsection_element.parent["id"],
            "type": "part_of",
            "context": "",
        }

        self.add_edge(edge_data)

    def parse_paragraph(self, subsection_element: Tag, paragraph_element: Tag):
        name = self.clean_text(paragraph_element.enum)
        header = self.clean_text(paragraph_element.header) if paragraph_element.header else ""
        text = self.clean_text(paragraph_element.find("text")) if paragraph_element.find("text") else ""

        quoted_block = subsection_element.parent.parent.name == "quoted-block"

        node_data = {
            "id": paragraph_element["id"],
            "number": name,
            "label": f"{name} {text[:100]} ... " if len(text) > 100 else f"{name} {text}",
            "type": "paragraph",
            "quoted": quoted_block,
            "text": f"{name} {header} {text}"
        
        } 

        self.add_node(node_data)

        edge_data = {
            "source_id": paragraph_element["id"],
            "target_id": subsection_element["id"] if not quoted_block else paragraph_element.parent["id"],
            "type": "part_of",
            "context": "",
        }

        self.add_edge(edge_data)
        
    def parse_subparagraph(self, paragraph_element: Tag, subpara_element: Tag):
        name = self.clean_text(subpara_element.enum)
        header = self.clean_text(subpara_element.header) if subpara_element.header else ""
        text = self.clean_text(subpara_element.find("text")) if subpara_element.find("text") else ""

        quoted_block = paragraph_element.parent.parent.parent.name == "quoted-block"

        node_data = {
            "id": subpara_element["id"],
            "number": name,
            "label": f"{name} {text[:100]} ... " if len(text) > 100 else f"{name} {text}",
            "type": "subparagraph",
            "quoted": quoted_block,
            "text": f"{name} {header} {text}"
        
        } 

        self.add_node(node_data)

        edge_data = {
            "source_id": subpara_element["id"],
            "target_id": paragraph_element["id"] if not quoted_block else subpara_element.parent["id"],
            "type": "part_of",
            "context": "",
        }

        self.add_edge(edge_data)

    def parse_clause(self, parent_element: Tag, child_element: Tag):
        name = self.clean_text(child_element.enum)
        text = self.clean_text(child_element.find("text")) if child_element.find("text") else ""

        quoted_block = parent_element.parent.parent.parent.parent.name == "quoted-block"

        node_data = {
            "id": child_element["id"],
            "number": name,
            "label": (text[:100] + "...") if len(text) > 100 else text,
            "type": "clause",
            "quoted": quoted_block,
            "text": f"{name} {text}"
        
        } 

        self.add_node(node_data)

        edge_data = {
            "source_id": child_element["id"],
            "target_id": parent_element["id"] if not quoted_block else child_element.parent["id"],
            "type": "part_of",
            "context": "",
        }

        self.add_edge(edge_data)

    def parse_subclause(self, parent_element: Tag, child_element: Tag):
        name = self.clean_text(child_element.enum)
        text = self.clean_text(child_element.find("text")) if child_element.find("text") else ""

        quoted_block = parent_element.parent.parent.parent.parent.parent.name == "quoted-block"

        node_data = {
            "id": child_element["id"],
            "number": name,
            "label": (text[:100] + "...") if len(text) > 100 else text,
            "type": "subclause",
            "quoted": quoted_block,
            "text": f"{name} {text}"
        
        } 

        self.add_node(node_data)

        edge_data = {
            "source_id": child_element["id"],
            "target_id": parent_element["id"] if not quoted_block else child_element.parent["id"],
            "type": "part_of",
            "context": "",
        }

        self.add_edge(edge_data)


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