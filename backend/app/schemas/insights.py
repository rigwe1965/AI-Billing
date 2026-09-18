from pydantic import BaseModel


class AskInsightIn(BaseModel):
    question: str


class AskInsightOut(BaseModel):
    answer: str
