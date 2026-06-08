from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AdminUser
from app.models.schemas import (
    CustomToolCreateRequest,
    CustomToolResponse,
    CustomToolTestRequest,
    CustomToolTestResponse,
    CustomToolUpdateRequest,
    UserAdminResponse,
    UserCreateRequest,
)
from app.services.custom_tool_service import (
    CustomToolConflictError,
    CustomToolError,
    CustomToolNotFoundError,
    create_custom_tool,
    delete_custom_tool,
    get_custom_tool_row,
    list_custom_tools,
    update_custom_tool,
)
from app.services.custom_tool_executor import test_custom_tool_connection
from app.services.tool_fabric_service import TOOL_ROLES
from app.services.user_service import (
    CannotDeleteLastAdminError,
    CannotDeleteSelfError,
    UserNotFoundError,
    UsernameTakenError,
    create_user,
    delete_user,
    list_users_with_stats,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserAdminResponse])
def list_users(admin: AdminUser, db: Session = Depends(get_db)):
    return list_users_with_stats(db)


@router.post("/users", response_model=UserAdminResponse, status_code=201)
def create_user_endpoint(body: UserCreateRequest, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        user = create_user(
            db,
            username=body.username,
            password=body.password,
            role=body.role,
            full_name=body.full_name,
        )
    except UsernameTakenError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    usage = list_users_with_stats(db)
    match = next((row for row in usage if row["id"] == user.id), None)
    if match:
        return match
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "created_at": user.created_at,
        "document_count": 0,
        "workflow_count": 0,
    }


@router.delete("/users/{user_id}", status_code=204)
def delete_user_endpoint(user_id: str, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        delete_user(db, user_id, actor_user_id=admin.id)
    except CannotDeleteSelfError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CannotDeleteLastAdminError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not delete user because related data is still linked. Contact support.",
        ) from exc


@router.get("/tool-fabric/roles")
def list_tool_fabric_roles(admin: AdminUser):
    return [
        {"id": rid, "label": spec["label"], "default": spec["default"], "builtin_options": spec["options"]}
        for rid, spec in TOOL_ROLES.items()
    ]


@router.get("/tool-fabric", response_model=list[CustomToolResponse])
def list_custom_tools_endpoint(admin: AdminUser, db: Session = Depends(get_db)):
    return list_custom_tools(db)


@router.post("/tool-fabric", response_model=CustomToolResponse, status_code=201)
def create_custom_tool_endpoint(body: CustomToolCreateRequest, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        return create_custom_tool(db, admin, body.model_dump())
    except CustomToolConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CustomToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/tool-fabric/{tool_row_id}", response_model=CustomToolResponse)
def update_custom_tool_endpoint(
    tool_row_id: str,
    body: CustomToolUpdateRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    try:
        return update_custom_tool(db, tool_row_id, admin, body.model_dump(exclude_unset=True))
    except CustomToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CustomToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/tool-fabric/{tool_row_id}", status_code=204)
def delete_custom_tool_endpoint(tool_row_id: str, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        delete_custom_tool(db, tool_row_id, admin)
    except CustomToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tool-fabric/{tool_row_id}/test", response_model=CustomToolTestResponse)
def test_custom_tool_endpoint(
    tool_row_id: str,
    body: CustomToolTestRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    tool = get_custom_tool_row(db, tool_row_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Custom tool not found")
    return test_custom_tool_connection(tool, body.sample_payload or None)
