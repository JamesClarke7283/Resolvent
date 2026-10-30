"""The same typed contract is used by the HTTP API, CLI, and MCP server."""

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MathError(ValueError):
    def __init__(self, message: str, code: str = "invalid_expression"):
        super().__init__(message)
        self.code = code


class MathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str = Field(default="simplify", max_length=40)
    expression: str = Field(min_length=1, max_length=8000)
    syntax: Literal["auto", "python", "latex"] = "auto"
    variable: str = "x"
    variables: list[str] = Field(default_factory=list, max_length=12)
    parameters: dict[str, Any] = Field(default_factory=dict)
    assumptions: dict[str, dict[str, bool]] = Field(default_factory=dict)
    precision: int = Field(default=16, ge=2, le=100)

    @field_validator("variable")
    @classmethod
    def valid_variable(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", value) or "__" in value:
            raise ValueError("Use a variable name such as x, theta, or x_1.")
        return value

    @field_validator("variables")
    @classmethod
    def valid_variables(cls, values: list[str]) -> list[str]:
        for value in values:
            cls.valid_variable(value)
        if len(values) != len(set(values)):
            raise ValueError("Variable names must be distinct.")
        return values

    @model_validator(mode="after")
    def bounded_parameters(self):
        if len(json.dumps(self.parameters)) > 24000:
            raise ValueError("Parameters are too large.")
        allowed = {"real", "positive", "negative", "nonnegative", "nonzero", "integer", "finite"}
        if len(self.assumptions) > 24:
            raise ValueError("At most 24 symbols can have assumptions.")
        for name, assumptions in self.assumptions.items():
            self.valid_variable(name)
            if not set(assumptions) <= allowed:
                raise ValueError(f"Supported assumptions: {', '.join(sorted(allowed))}.")
        return self


class MathResult(BaseModel):
    id: str
    operation: str
    input: str
    input_latex: str
    result: str
    latex: str
    numeric: str | None = None
    data: Any = None
    status: Literal["ok", "unevaluated"] = "ok"
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: float
    plot: dict[str, Any] | None = None


class Worksheet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled worksheet", min_length=1, max_length=120)
    cells: list[MathRequest] = Field(default_factory=list, max_length=100)
