from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import (
    CORSMiddleware,
)  # https://fastapi.tiangolo.com/tutorial/cors/

# from dotenv import load_dotenv

# load_dotenv()

# from config import settings

# from chat.completion import router as completion_router
from chat.rag import router as rag_router
# from chat.chat_router import chat_router
# from chat.chat_with_context import chat_with_context_router


app = FastAPI()

# https://fastapi.tiangolo.com/tutorial/cors/
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    # "https://build-ai-driven-web-applications.vercel.app",
    # "https://gen-ai-template-one.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class HelloWorldParams(BaseModel):
    content: Optional[str] = "This is an example param."


@app.get("/hello-world")
async def root(params: HelloWorldParams = Depends()):
    return {"message": "Hello World", "params": params.model_dump()}


# app.include_router(completion_router)
app.include_router(rag_router)
# app.include_router(chat_router)
# app.include_router(chat_with_context_router)
