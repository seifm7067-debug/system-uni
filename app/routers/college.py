from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud.college import (
    create_college,
    delete_college,
    read_college,
    read_colleges,
    update_college,
)
from app.database import get_db
from app.models.user import User
from app.schemas.college import CollegeCreate, CollegeResponseSchema, CollegeUpdate
from app.security.auth import require_admin, require_authenticated_user

router = APIRouter()


@router.post("/colleges/", response_model=CollegeResponseSchema, status_code=status.HTTP_201_CREATED)
def create_college_endpoint(
    college: CollegeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_college(db, college)


@router.get("/colleges/{college_id}", response_model=CollegeResponseSchema)
def get_college(
    college_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_college(db, college_id)


@router.get("/colleges/", response_model=list[CollegeResponseSchema])
def get_colleges(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_colleges(db, skip=skip, limit=limit)


@router.put("/colleges/{college_id}", response_model=CollegeResponseSchema)
def update_college_endpoint(
    college_id: int,
    college: CollegeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return update_college(db, college, college_id)


@router.delete("/colleges/{college_id}")
def delete_college_endpoint(
    college_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_college(db, college_id)
