from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Checkin, Focus, Plan, Task

SHANGHAI = timezone(timedelta(hours=8))


def today():
    return datetime.now(SHANGHAI).date()


def serialize_plan(db: Session, plan: Plan):
    tasks = db.scalars(
        select(Task).where(Task.plan_id == plan.id).order_by(Task.position, Task.created_at, Task.id)
    ).all()
    done = sum(task.done for task in tasks)
    return {
        "id": plan.id,
        "title": plan.title,
        "description": plan.description,
        "tasks": [{"id": t.id, "title": t.title, "done": t.done, "minutes": t.minutes} for t in tasks],
        "progress": round(done / len(tasks) * 100) if tasks else 0,
        "created_at": plan.created_at,
    }


def create_plan(db: Session, user_id: str, title: str, description: str, tasks: list):
    plan = Plan(user_id=user_id, title=title, description=description)
    db.add(plan)
    db.flush()
    for position, task in enumerate(tasks):
        db.add(Task(user_id=user_id, plan_id=plan.id, title=task["title"], minutes=task["minutes"], position=position))
    db.flush()
    return plan


def stats(db: Session, user_id: str):
    current = today()
    checkins = db.scalars(select(Checkin).where(Checkin.user_id == user_id)).all()
    days = {item.day for item in checkins}
    cursor = current if current in days else current - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    focuses = db.scalars(select(Focus).where(Focus.user_id == user_id, Focus.completed_at.is_not(None))).all()
    daily = {}
    for item in focuses:
        day = item.completed_at.replace(tzinfo=timezone.utc).astimezone(SHANGHAI).date().isoformat()
        daily[day] = daily.get(day, 0) + item.minutes
    tasks = db.scalars(select(Task).where(Task.user_id == user_id)).all()
    return {
        "today": current.isoformat(),
        "today_minutes": daily.get(current.isoformat(), 0),
        "total_minutes": sum(f.minutes for f in focuses),
        "focus_count": len(focuses),
        "streak": streak,
        "checkin_count": len(days),
        "checked_in": current in days,
        "task_count": len(tasks),
        "completed_tasks": sum(t.done for t in tasks),
        "week": [
            {
                "day": (current - timedelta(days=i)).isoformat(),
                "minutes": daily.get((current - timedelta(days=i)).isoformat(), 0),
            }
            for i in range(6, -1, -1)
        ],
        "heatmap": [
            {
                "day": (current - timedelta(days=i)).isoformat(),
                "checked": current - timedelta(days=i) in days,
                "minutes": daily.get((current - timedelta(days=i)).isoformat(), 0),
            }
            for i in range(363, -1, -1)
        ],
    }
