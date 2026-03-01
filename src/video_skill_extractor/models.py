from pydantic import BaseModel, Field, model_validator


class Step(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class TranscriptSegment(BaseModel):
    segment_id: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_times(self) -> "TranscriptSegment":
        if self.end_s < self.start_s:
            raise ValueError("end_s must be >= start_s")
        return self


class TutorialStep(BaseModel):
    step_id: str = Field(min_length=1)
    source_segment_id: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    clip_start_s: float = Field(ge=0)
    clip_end_s: float = Field(ge=0)
    instruction_text: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _validate_step_times(self) -> "TutorialStep":
        if self.end_s < self.start_s:
            raise ValueError("end_s must be >= start_s")
        if self.clip_end_s < self.clip_start_s:
            raise ValueError("clip_end_s must be >= clip_start_s")
        return self


class FrameCandidate(BaseModel):
    segment_id: str = Field(min_length=1)
    timestamp_s: float = Field(ge=0)
    label: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    clip_start_s: float = Field(ge=0)
    clip_end_s: float = Field(ge=0)

    @model_validator(mode="after")
    def _validate_clip_window(self) -> "FrameCandidate":
        if self.clip_end_s < self.clip_start_s:
            raise ValueError("clip_end_s must be >= clip_start_s")
        return self
