"""Settings endpoints (scoring curve, etc.)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.scoring_curve import load_curve, save_curve
from server.elimination_marks import load_marks, save_marks

router = APIRouter(prefix="/api/settings", tags=["settings"])


class CurvePoint(BaseModel):
    t: float = Field(ge=0.0, le=1.0)
    points: int = Field(ge=0)


class ScoringCurve(BaseModel):
    points: list[CurvePoint]


@router.get("/scoring", response_model=ScoringCurve)
def get_scoring() -> ScoringCurve:
    return ScoringCurve(
        points=[CurvePoint(t=t, points=p) for t, p in load_curve()]
    )


@router.put("/scoring", response_model=ScoringCurve)
def put_scoring(curve: ScoringCurve) -> ScoringCurve:
    if len(curve.points) < 2:
        raise HTTPException(400, "Need at least 2 control points")
    saved = save_curve([(p.t, p.points) for p in curve.points])
    return ScoringCurve(points=[CurvePoint(t=t, points=p) for t, p in saved])


class EliminationMarks(BaseModel):
    marks: list[float] = Field(min_length=2, max_length=2)


@router.get("/elimination", response_model=EliminationMarks)
def get_elimination() -> EliminationMarks:
    return EliminationMarks(marks=list(load_marks()))


@router.put("/elimination", response_model=EliminationMarks)
def put_elimination(payload: EliminationMarks) -> EliminationMarks:
    for m in payload.marks:
        if not (0.0 < m < 1.0):
            raise HTTPException(400, "marks must be strictly between 0 and 1")
    saved = save_marks(payload.marks)
    return EliminationMarks(marks=list(saved))
