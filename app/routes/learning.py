from datetime import timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.models import Checkin, Focus, Plan, Task, now
from app.schemas import CheckinInput, FocusInput, PlanInput, TaskInput, TaskUpdate
from app.security import DB, CurrentUser
from app.services.learning import create_plan, serialize_plan, stats, today

router = APIRouter(prefix="/api", tags=["学习"])


def owned(db, model, identifier, user_id):
    value = db.get(model, identifier)
    if not value or value.user_id != user_id:
        raise HTTPException(404, "记录不存在")
    return value


@router.get("/stats")
def statistics(user: CurrentUser, db: DB):
    return stats(db, user.id)


@router.get("/plans")
def plans(user: CurrentUser, db: DB):
    return [
        serialize_plan(db, p)
        for p in db.scalars(select(Plan).where(Plan.user_id == user.id).order_by(Plan.created_at.desc()))
    ]


@router.post("/plans", status_code=201)
def add_plan(body: PlanInput, user: CurrentUser, db: DB):
    plan = create_plan(db, user.id, body.title, body.description, [t.model_dump() for t in body.tasks])
    db.commit()
    return serialize_plan(db, plan)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: str, user: CurrentUser, db: DB):
    plan = owned(db, Plan, plan_id, user.id)
    db.delete(plan)
    db.commit()


@router.post("/plans/{plan_id}/tasks", status_code=201)
def add_task(plan_id: str, body: TaskInput, user: CurrentUser, db: DB):
    owned(db, Plan, plan_id, user.id)
    last_position = db.scalar(select(func.max(Task.position)).where(Task.plan_id == plan_id))
    task = Task(
        user_id=user.id,
        plan_id=plan_id,
        position=(last_position if last_position is not None else -1) + 1,
        **body.model_dump(),
    )
    db.add(task)
    db.commit()
    return {"id": task.id, "title": task.title, "done": task.done, "minutes": task.minutes}


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate, user: CurrentUser, db: DB):
    task = owned(db, Task, task_id, user.id)
    task.done = body.done
    db.commit()
    return {"id": task.id, "done": task.done}


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, user: CurrentUser, db: DB):
    db.delete(owned(db, Task, task_id, user.id))
    db.commit()


@router.post("/checkins")
def checkin(body: CheckinInput, user: CurrentUser, db: DB):
    db.add(Checkin(user_id=user.id, day=today(), note=body.note))
    duplicate = False
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = True
    return {"duplicate": duplicate, **stats(db, user.id)}


def focus_data(focus):
    return {
        "id": focus.id,
        "minutes": focus.minutes,
        "task_id": focus.task_id,
        "started_at": focus.started_at.replace(tzinfo=timezone.utc).isoformat(),
        "ends_at": (focus.started_at.replace(tzinfo=timezone.utc) + timedelta(minutes=focus.minutes)).isoformat(),
        "completed": focus.completed_at is not None,
    }


@router.get("/focus/active")
def active_focus(user: CurrentUser, db: DB):
    focus = db.scalar(select(Focus).where(Focus.user_id == user.id, Focus.completed_at.is_(None)))
    return focus_data(focus) if focus else None


@router.post("/focus/start")
def start_focus(body: FocusInput, user: CurrentUser, db: DB):
    if body.task_id:
        owned(db, Task, body.task_id, user.id)
    existing = db.scalar(select(Focus).where(Focus.user_id == user.id, Focus.request_id == body.request_id))
    if existing:
        return focus_data(existing)
    active = db.scalar(select(Focus).where(Focus.user_id == user.id, Focus.completed_at.is_(None)))
    if active:
        raise HTTPException(409, "已有专注进行中，请完成或取消后重试")
    focus = Focus(user_id=user.id, **body.model_dump())
    db.add(focus)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        focus = db.scalar(select(Focus).where(Focus.user_id == user.id, Focus.request_id == body.request_id))
        if not focus:
            raise HTTPException(409, "已有专注进行中，请刷新页面") from None
    return focus_data(focus)


@router.post("/focus/{focus_id}/complete")
def complete_focus(focus_id: str, user: CurrentUser, db: DB):
    focus = owned(db, Focus, focus_id, user.id)
    if focus.completed_at:
        return {"duplicate": True, **focus_data(focus)}
    if now() < focus.started_at.replace(tzinfo=timezone.utc) + timedelta(minutes=focus.minutes):
        raise HTTPException(409, "专注时间尚未结束")
    focus.completed_at = now()
    db.commit()
    return {"duplicate": False, **focus_data(focus)}


@router.delete("/focus/{focus_id}", status_code=204)
def cancel_focus(focus_id: str, user: CurrentUser, db: DB):
    focus = owned(db, Focus, focus_id, user.id)
    if focus.completed_at:
        raise HTTPException(409, "已完成的专注不可取消")
    db.execute(delete(Focus).where(Focus.id == focus.id, Focus.completed_at.is_(None)))
    db.commit()
