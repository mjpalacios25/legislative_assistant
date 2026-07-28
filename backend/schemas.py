from typing import Literal
from pydantic import BaseModel, Field

bill_parts = Literal["title", "part", "section", "subsection", "paragraph", "subparagraph", "clause", "subclause"]

class Legislation(BaseModel):
    congress: int
    number: str
    originChamber: str
    originChamberCode: str
    title: str
    type: str
    updateDate: str
    updateDateIncludingText: str
    url: str

    #add function to do.... 

class bill_text(BaseModel):
    section: bill_parts
    text: (str) = Field(description = "text of provided bill part")

class bill_part_relationship(BaseModel):
    type: (str) = Field(description="relationship between one bill part and another")

class legislator_info(BaseModel):
    chamber: Literal["senate", "house"]
    name: (str) = Field(description="name of legislator")
    state: (str) = Field(description="state name (non abbriviated)")
    district: str | None = None



