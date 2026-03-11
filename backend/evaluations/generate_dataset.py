import instructor
from asyncio import Semaphore
import asyncio
from pydantic import BaseModel
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext
from tqdm.asyncio import tqdm_asyncio
from tenacity import retry, stop_after_attempt, wait_fixed
from openai import AsyncOpenAI
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent)) 
from config.main import PUBLIC_DIR
import random

### Goal here is to create an evaluation pipeline that genereates synthetic questions and evaluates against those questions. 

client = instructor.from_openai(
    AsyncOpenAI(
        base_url="http://localhost:8080/v1",
        api_key="mlx",  # ignored but required
        # max_tokens = 4096
    ),
    mode=instructor.Mode.JSON,
)



# Create Pydantic models to represent the data we will work with throughout the processes

class Chunk(BaseModel):
    chunk_id: str
    text: str

class Question(BaseModel):
    chain_of_thought: str
    question: str

class ChunkEval(BaseModel):
    chunk_id: str
    question: str
    chunk: str

# Load subsection samples
path = Path(PUBLIC_DIR / "Subsections.json")
Subsections = json.load(open(path)) if path.exists() else []

# Create dataset of cases to evaluate the RAG application

if Subsections:
    SubsectionSample = Subsections[0:51]

    constraints = [
        "Add in irrelevant context that isn't mentioned in the legislative text (e.g., time of day, current year, a school district)",
        "Make questions vague rather than cite specific section numbers of the bill",
    ]

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    async def generateQuestions(chunk: Chunk, sem:Semaphore) -> ChunkEval:
        async with sem:

            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model="Qwen/Qwen3-4B-MLX-4bit",
                    messages=[
                        {
                            "role": "user",
                            "content": """
                    Generate a hypothetical question that can be answered using the following section of legislative text.

                    Legislative text:
                    {{ snippet }}

                    Rules
                    - The question should be at most 2 sentences long
                    - The question must be answerable using the provided legislative text or at most with a small tweak
                    - if necessary, make questions more challenging using the following constraint of {{constraint}}
                    """,
                        }
                    ],
                    response_model=Question,
                    context={
                        "snippet": chunk.text,
                        "constraint": random.choice(constraints)
                    },
                ),
                timeout=60,
            )

            return ChunkEval(
                chunk_id=chunk.chunk_id,
                question=resp.question,
                chunk=chunk.text
            )

    async def main():

        sem = asyncio.Semaphore(2)

        print("=> generating dataset! ")

        dataset = [
            Chunk(chunk_id= str(index) , text=item)
            for index, item in enumerate(SubsectionSample) 
        ]

        print("=> generating quesitons: ")

        coros = []

        numSamples = 2

        for chunk in dataset:
            for _ in range(numSamples):
                coros.append(generateQuestions(chunk, sem))

        questions: list[ChunkEval] = await tqdm_asyncio.gather(*coros)

        # Save dataset

        print("=> saving dataset... ")

        cases = [
            Case(
                name=f"question_{index}",
                inputs=question.question,
                expected_output=[question.chunk],
                metadata={"chunk_id": question.chunk_id},
            )
            for index, question in enumerate(questions)
        ]

        dataset = Dataset(cases=cases)
        dataset.to_file(PUBLIC_DIR / "questions.yaml")

        return questions

    if __name__ == "__main__":
        asyncio.run(main())

    

# Evaluation funcitons and Experiments to use in the evaluation

# Run the eval
