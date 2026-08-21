from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    abha_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)

    chronic_conditions: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    allergies: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    pregnancy_or_recent_childbirth: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    screenings: Mapped[list["Screening"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan"
    )


class Screening(Base):
    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"),
        nullable=False,
        index=True
    )

    # Symptoms selected by the patient
    symptoms: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list
    )

    # Vitals
    temperature: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    blood_pressure: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    blood_sugar: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    spo2: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    pulse: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    # AI / triage result
    risk_score: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    priority: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    advice: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    referral_window: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    risk_signals: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    patient: Mapped["Patient"] = relationship(
        back_populates="screenings"
    )