from bs4 import BeautifulSoup, Tag #for XML parsing
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.main import PUBLIC_DIR
import re

#


# Create a list of subsections in Title I of ESSA

with open(PUBLIC_DIR / "BILLS-114s1177enr.xml") as bill_xml:
    soup = BeautifulSoup(bill_xml, "xml")

def parseSections(xml_soup: BeautifulSoup):
    allSubsections = []
    leg = xml_soup.bill
    titleI = leg.find(id = "HBCB1043F254B467C880CA4632EB8661D")
    partATitleI = titleI.find(id = "H37898CE342274356A2E0C2E54F77E786")
    for section in partATitleI.find_all("section"):
        for subsection in section.find_all("subsection"):
            # Use stripped_strings + join to match how build_knowledge_graph.py
            # stores text in Neo4j nodes (both put one space between XML elements).
            strings = [s.replace("\n", "") for s in subsection.stripped_strings]
            text = " ".join(strings)
            allSubsections.append(text)
    return allSubsections

Subsections = parseSections(soup)

# Save
with open(PUBLIC_DIR / "Subsections.json", "w") as f:
    json.dump(Subsections, f)