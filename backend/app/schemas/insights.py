from pydantic import BaseModel, Field


class AskInsightIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskInsightOut(BaseModel):
    answer: str
