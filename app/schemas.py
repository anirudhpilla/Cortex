from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AdminRead(BaseModel):
    id: int
    email: EmailStr
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AdminRead


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    repository_id: int | None = Field(default=None, gt=0)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank")
        return value


class Source(BaseModel):
    id: str
    path: str
    text: str
    repository_id: int | None = None
    start_index: int | None = None
    end_index: int | None = None
    page_number: int | None = None


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(max_length=12000)
    source_ids: list[str] = Field(max_length=20)
    insufficient_context: bool

    @field_validator("source_ids")
    @classmethod
    def unique_source_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate source IDs")
        return value


class ChatResponse(Answer):
    sources: list[Source]
    provider: str


class Evidence(BaseModel):
    id: str
    path: str
    text: str
