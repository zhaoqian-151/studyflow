import re
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("请输入有效的邮箱")
        return value


class Register(Credentials):
    name: str = Field(min_length=1, max_length=60)


class TaskInput(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    minutes: int = Field(default=25, ge=5, le=180)


class PlanInput(BaseModel):
    title: Title
    description: str = Field(default="", max_length=10000)
    tasks: list[TaskInput] = Field(default_factory=list, max_length=30)


class TaskUpdate(BaseModel):
    done: bool


class CheckinInput(BaseModel):
    note: str = Field(default="", max_length=500)


class FocusInput(BaseModel):
    minutes: int = Field(default=25, ge=1, le=180)
    task_id: str | None = None
    request_id: str = Field(min_length=8, max_length=80)


class DocumentInput(BaseModel):
    title: Title
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200000)]


class Question(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    document_id: str | None = Field(default=None, min_length=1, max_length=64)


class AgentInput(BaseModel):
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=2000)]


class AgentDraft(BaseModel):
    title: Title
    summary: str = Field(min_length=1, max_length=2000)
    tasks: list[TaskInput] = Field(min_length=1, max_length=12)


class PreferenceInput(BaseModel):
    preference: str = Field(max_length=1000)
