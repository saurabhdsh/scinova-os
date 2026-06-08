"""Shared project workspaces for team collaboration."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.db_models import Project, ProjectMember, User


def project_ids_for_user(db: Session, user_id: str) -> list[str]:
    rows = db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user_id).all()
    return [r[0] for r in rows]


def user_can_access_project(db: Session, user_id: str, project_id: str) -> bool:
    if not project_id:
        return False
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    return member is not None


def assert_project_access(db: Session, user_id: str, project_id: str) -> ProjectMember:
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this project")
    return member


def list_projects_for_user(db: Session, user_id: str) -> list[dict]:
    members = (
        db.query(ProjectMember, Project)
        .join(Project, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == user_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [
        {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "owner_id": project.owner_id,
            "role": member.role,
            "created_at": project.created_at,
        }
        for member, project in members
    ]


def create_project(db: Session, user: User, name: str, description: str | None = None) -> Project:
    project = Project(
        name=name.strip(),
        description=(description or "").strip() or None,
        owner_id=user.id,
    )
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(project)
    return project


def add_project_member(
    db: Session,
    project_id: str,
    actor_user_id: str,
    username: str,
    role: str = "member",
) -> ProjectMember:
    assert_project_access(db, actor_user_id, project_id)
    actor = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == actor_user_id,
    ).first()
    if actor.role != "owner":
        raise HTTPException(status_code=403, detail="Only project owners can add members")

    target = db.query(User).filter(User.username == username.strip()).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")

    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == target.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a project member")

    member = ProjectMember(project_id=project_id, user_id=target.id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def list_project_members(db: Session, user_id: str, project_id: str) -> list[dict]:
    assert_project_access(db, user_id, project_id)
    rows = (
        db.query(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project_id)
        .all()
    )
    return [
        {
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": member.role,
            "joined_at": member.created_at,
        }
        for member, user in rows
    ]
