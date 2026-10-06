from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import FarmerProfile
from app.schemas import FarmerCreate, FarmerOut

router = APIRouter(prefix="/api/farmers", tags=["farmers"])

@router.post("", response_model=FarmerOut)
def create_farmer(payload: FarmerCreate, db: Session = Depends(get_db)):
    farmer = FarmerProfile(**payload.model_dump())
    db.add(farmer)
    db.commit()
    db.refresh(farmer)
    return farmer

