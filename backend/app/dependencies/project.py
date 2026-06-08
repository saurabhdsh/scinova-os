"""Optional active project from request header."""

from typing import Annotated

from fastapi import Header

OptionalProjectId = Annotated[str | None, Header(alias="X-Project-Id")]
