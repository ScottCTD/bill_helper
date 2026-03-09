from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.services.agent.payload_normalization import normalize_optional_category, normalize_required_text
from backend.validation.finance_names import normalize_entity_name, normalize_tag_name


class CreateTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        normalized = normalize_optional_category(value)
        if normalized is None:
            raise ValueError("type cannot be empty")
        return normalized


class UpdateTagPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    type: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str | None) -> str | None:
        return normalize_optional_category(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateTagPatchPayload:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class UpdateTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    patch: UpdateTagPatchPayload

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class DeleteTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class CreateEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = normalize_optional_category(value)
        if normalized is None:
            raise ValueError("category cannot be empty")
        return normalized


class UpdateEntityPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return normalize_optional_category(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateEntityPatchPayload:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class UpdateEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    patch: UpdateEntityPatchPayload

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class DeleteEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class CreateAccountPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    currency_code: str = Field(min_length=3, max_length=3)
    is_active: bool = True
    markdown_body: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        return normalize_required_text(value).upper()


class UpdateAccountPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None
    markdown_body: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value).upper()

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateAccountPatchPayload:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class UpdateAccountPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    patch: UpdateAccountPatchPayload

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class DeleteAccountPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized
