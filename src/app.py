"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker, selectinload

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(Path(__file__).parent, "static")),
    name="static",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./activities.db",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Activity(Base):
    __tablename__ = "activities"

    name = Column(String, primary_key=True, index=True)
    description = Column(String, nullable=False)
    schedule = Column(String, nullable=False)
    max_participants = Column(Integer, nullable=False)

    participants = relationship(
        "Participant",
        back_populates="activity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("activity_name", "email", name="uq_activity_email"),)

    id = Column(Integer, primary_key=True, index=True)
    activity_name = Column(String, ForeignKey("activities.name"), nullable=False)
    email = Column(String, nullable=False)

    activity = relationship("Activity", back_populates="participants")


INITIAL_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def serialize_activity(activity: Activity):
    return {
        "description": activity.description,
        "schedule": activity.schedule,
        "max_participants": activity.max_participants,
        "participants": [participant.email for participant in activity.participants],
    }


def seed_initial_data():
    db = SessionLocal()
    try:
        activity_count = db.query(Activity).count()
        if activity_count > 0:
            return

        for name, details in INITIAL_ACTIVITIES.items():
            activity = Activity(
                name=name,
                description=details["description"],
                schedule=details["schedule"],
                max_participants=details["max_participants"],
            )
            db.add(activity)
            for email in details["participants"]:
                participant = Participant(activity_name=name, email=email)
                db.add(participant)
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_initial_data()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities(db: Session = Depends(get_db)):
    activities = db.query(Activity).options(selectinload(Activity.participants)).all()
    return {activity.name: serialize_activity(activity) for activity in activities}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, db: Session = Depends(get_db)):
    """Sign up a student for an activity"""
    activity = (
        db.query(Activity)
        .options(selectinload(Activity.participants))
        .filter(Activity.name == activity_name)
        .first()
    )
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    if any(participant.email == email for participant in activity.participants):
        raise HTTPException(status_code=400, detail="Student is already signed up")

    if len(activity.participants) >= activity.max_participants:
        raise HTTPException(status_code=400, detail="Activity is full")

    participant = Participant(activity_name=activity_name, email=email)
    db.add(participant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Student is already signed up")

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, db: Session = Depends(get_db)):
    """Unregister a student from an activity"""
    activity = db.query(Activity).filter(Activity.name == activity_name).first()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    participant = (
        db.query(Participant)
        .filter(Participant.activity_name == activity_name, Participant.email == email)
        .first()
    )
    if participant is None:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity",
        )

    db.delete(participant)
    db.commit()
    return {"message": f"Unregistered {email} from {activity_name}"}
