from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Team, User
from schemas import TeamOut, TeamCreate, UserOut
from auth import get_current_user, require_admin_or_manager

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=List[TeamOut])
def list_teams(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Team).order_by(Team.name).all()


@router.post("", response_model=TeamOut)
def create_team(body: TeamCreate, db: Session = Depends(get_db), _: User = Depends(require_admin_or_manager)):
    if db.query(Team).filter(Team.name == body.name).first():
        raise HTTPException(status_code=400, detail="Team name already exists")
    team = Team(name=body.name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.put("/{team_id}", response_model=TeamOut)
def update_team(team_id: UUID, body: TeamCreate, db: Session = Depends(get_db), _: User = Depends(require_admin_or_manager)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    team.name = body.name
    db.commit()
    db.refresh(team)
    return team


@router.delete("/{team_id}")
def delete_team(team_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_admin_or_manager)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    db.delete(team)
    db.commit()
    return {"message": "deleted"}


@router.get("/{team_id}/members", response_model=List[UserOut])
def list_team_members(team_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(User).filter(User.team_id == team_id).order_by(User.name).all()
