"""PUBLIC_STANDARD: bounded transcript recovery and saved-field render requests."""
from typing import Literal
import json
from pydantic import Field, model_validator
from .reference_experiment import ReferenceContract
from .scientific_workflow import ScientificExperimentContext


class ConversationMessage(ReferenceContract):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=32_000)


class StudioConversationSave(ReferenceContract):
    revision: int = Field(default=0, ge=0)
    messages: list[ConversationMessage] = Field(default_factory=list, max_length=1000)
    active_scientific_job_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{32}$')
    selected_fields: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode='after')
    def bounded_transcript(self):
        if len(json.dumps([m.model_dump() for m in self.messages])) > 2_000_000:
            raise ValueError('Conversation exceeds the recoverable transcript limit')
        if any(len(name) > 80 for name in self.selected_fields):
            raise ValueError('Invalid saved field selection')
        return self


class StudioConversation(StudioConversationSave):
    title: str = Field(default='Scientific conversation',max_length=150)
    conversation_id: str = Field(pattern=r'^[0-9a-f]{32}$')
    updated_at: str
    expires_at: str
    scientific_context: ScientificExperimentContext | None = None
    recovery_message: str | None = None


class ScientificFigureRequest(ReferenceContract):
    fields: tuple[str, ...] = Field(min_length=1, max_length=4,strict=False)
    display_scale: float = Field(default=1., ge=.2, le=2.)
    dpi: Literal[150, 200] = 200

    @model_validator(mode='after')
    def unique_fields(self):
        if len(set(self.fields)) != len(self.fields) or any(len(name)>80 for name in self.fields):
            raise ValueError('Choose one to four unique saved fields')
        return self
