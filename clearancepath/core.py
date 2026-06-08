"""Core engine for CLEARANCEPATH.

Real, deterministic clearance-hygiene logic grounded in the actual federal
personnel-security framework:

  * SF-86 / e-QIP periodic reinvestigation (PR) cadence. Historically the
    Tier-5 (formerly SSBI) reinvestigation cycle is 5 years for TS/SCI and
    Tier-3 is 10 years for Secret. Under Trusted Workforce 2.0 / Continuous
    Vetting (CV) the calendar PR is being deprecated, but the 5/10-year
    "stale of record" horizons remain the practical hygiene checkpoints.

  * SEAD-3 (Reporting Requirements for Personnel with Access to Classified
    Information or Who Hold a Sensitive Position) — self-reportable events
    (foreign travel, foreign contacts, financial issues, arrests, etc.).
    Reportable events generally must be reported promptly; foreign travel
    is reportable in advance. We treat unreported events past a grace
    window as findings.

  * SEAD-4 (National Security Adjudicative Guidelines A-M) — open
    adjudicative concerns (e.g. Guideline F financial, Guideline G alcohol)
    that are flagged but not yet mitigated/adjudicated.

  * Training currency — annual refresh items (security refresher,
    insider-threat awareness, derivative-classifier, NATO, etc.).

Everything is computed against an explicit "as of" date so output is
reproducible and testable. No network, no third-party deps.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

# Reinvestigation horizon (days) by eligibility level. Calendar PR cadence.
_PR_HORIZON_DAYS = {
    "TS/SCI": 5 * 365,
    "TS": 5 * 365,
    "SECRET": 10 * 365,
    "CONFIDENTIAL": 15 * 365,
}

# When PR is within this many days of the horizon, warn ("due soon").
_PR_DUE_SOON_DAYS = 180

# SEAD-3 reporting grace: an event must be self-reported within this window.
_REPORT_GRACE_DAYS = 30
# Foreign travel is reportable *in advance*; lateness is treated stricter.
_TRAVEL_GRACE_DAYS = 0

# Training validity (days) by item. Default to one year if unknown.
_TRAINING_VALIDITY_DAYS = {
    "security_refresher": 365,
    "insider_threat": 365,
    "derivative_classifier": 365,
    "nato": 365,
    "ci_awareness": 365,
    "opsec": 365,
}
_DEFAULT_TRAINING_VALIDITY_DAYS = 365
_TRAINING_DUE_SOON_DAYS = 30


class Severity(IntEnum):
    OK = 0
    INFO = 1
    WARN = 2
    CRITICAL = 3

    @property
    def label(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_date(value: Any) -> Optional[_dt.date]:
    """Parse an ISO date (YYYY-MM-DD) or date object. None/'' -> None."""
    if value is None or value == "":
        return None
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"invalid date {value!r}; expected YYYY-MM-DD") from exc


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Reportable:
    """A SEAD-3 self-reportable event."""

    kind: str                       # e.g. "foreign_travel", "arrest", "financial"
    occurred: _dt.date
    reported: Optional[_dt.date] = None
    detail: str = ""

    @property
    def is_travel(self) -> bool:
        return self.kind.lower() in ("foreign_travel", "travel")


@dataclass
class Training:
    """A training/currency item."""

    item: str
    completed: Optional[_dt.date] = None
    validity_days: Optional[int] = None

    def horizon(self) -> int:
        if self.validity_days:
            return self.validity_days
        return _TRAINING_VALIDITY_DAYS.get(
            self.item.lower(), _DEFAULT_TRAINING_VALIDITY_DAYS
        )


@dataclass
class Person:
    name: str
    eligibility: str = "SECRET"      # CONFIDENTIAL / SECRET / TS / TS/SCI
    last_investigation: Optional[_dt.date] = None
    sead4_concerns: list[str] = field(default_factory=list)
    reportables: list[Reportable] = field(default_factory=list)
    trainings: list[Training] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Person":
        if "name" not in d:
            raise ValueError("person record missing required 'name'")
        elig = str(d.get("eligibility", "SECRET")).upper().replace(" ", "")
        # normalize a couple of common spellings
        elig = {"TSSCI": "TS/SCI", "TOPSECRET": "TS"}.get(elig, elig)
        reportables = []
        for r in d.get("reportables", []) or []:
            occ = parse_date(r.get("occurred"))
            if occ is None:
                raise ValueError(
                    f"reportable for {d['name']!r} missing 'occurred' date"
                )
            reportables.append(
                Reportable(
                    kind=str(r.get("kind", "unspecified")),
                    occurred=occ,
                    reported=parse_date(r.get("reported")),
                    detail=str(r.get("detail", "")),
                )
            )
        trainings = []
        for t in d.get("trainings", []) or []:
            trainings.append(
                Training(
                    item=str(t.get("item", "unspecified")),
                    completed=parse_date(t.get("completed")),
                    validity_days=t.get("validity_days"),
                )
            )
        return cls(
            name=str(d["name"]),
            eligibility=elig,
            last_investigation=parse_date(d.get("last_investigation")),
            sead4_concerns=[str(c) for c in (d.get("sead4_concerns") or [])],
            reportables=reportables,
            trainings=trainings,
        )


@dataclass
class Finding:
    category: str
    severity: Severity
    message: str
    days: Optional[int] = None       # +overdue / -remaining context

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity.label,
            "message": self.message,
            "days": self.days,
        }


@dataclass
class HygieneReport:
    name: str
    eligibility: str
    findings: list[Finding]

    @property
    def status(self) -> Severity:
        return max((f.severity for f in self.findings), default=Severity.OK)

    def to_dict(self) -> dict[str, Any]:
        counts = {s.label: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.label] += 1
        return {
            "name": self.name,
            "eligibility": self.eligibility,
            "status": self.status.label,
            "counts": counts,
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Assessment engine
# ---------------------------------------------------------------------------

def _assess_investigation(p: Person, as_of: _dt.date) -> Finding:
    horizon = _PR_HORIZON_DAYS.get(p.eligibility, _PR_HORIZON_DAYS["SECRET"])
    if p.last_investigation is None:
        return Finding(
            "investigation",
            Severity.CRITICAL,
            f"no investigation of record for {p.eligibility} eligibility",
        )
    age = (as_of - p.last_investigation).days
    overdue = age - horizon
    if overdue > 0:
        return Finding(
            "investigation",
            Severity.CRITICAL,
            f"reinvestigation overdue by {overdue}d "
            f"(record {age}d old vs {horizon}d {p.eligibility} horizon)",
            days=overdue,
        )
    remaining = -overdue
    if remaining <= _PR_DUE_SOON_DAYS:
        return Finding(
            "investigation",
            Severity.WARN,
            f"reinvestigation due in {remaining}d",
            days=-remaining,
        )
    return Finding(
        "investigation",
        Severity.OK,
        f"record current; {remaining}d until {p.eligibility} horizon",
        days=-remaining,
    )


def _assess_reportable(r: Reportable, as_of: _dt.date) -> Finding:
    grace = _TRAVEL_GRACE_DAYS if r.is_travel else _REPORT_GRACE_DAYS
    label = r.detail or r.kind
    if r.reported is None:
        elapsed = (as_of - r.occurred).days
        if elapsed > grace:
            return Finding(
                "sead3",
                Severity.CRITICAL,
                f"unreported {r.kind} ({label}); {elapsed}d since event, "
                f"grace {grace}d",
                days=elapsed - grace,
            )
        return Finding(
            "sead3",
            Severity.WARN,
            f"{r.kind} ({label}) not yet reported; {grace - elapsed}d "
            f"of grace remaining",
            days=-(grace - elapsed),
        )
    lateness = (r.reported - r.occurred).days
    if lateness > grace:
        return Finding(
            "sead3",
            Severity.WARN,
            f"{r.kind} ({label}) reported {lateness}d after event "
            f"(grace {grace}d) — late self-report on record",
            days=lateness - grace,
        )
    return Finding(
        "sead3",
        Severity.OK,
        f"{r.kind} ({label}) reported within grace",
    )


def _assess_training(t: Training, as_of: _dt.date) -> Finding:
    horizon = t.horizon()
    if t.completed is None:
        return Finding(
            "training",
            Severity.CRITICAL,
            f"{t.item} never completed",
        )
    age = (as_of - t.completed).days
    overdue = age - horizon
    if overdue > 0:
        return Finding(
            "training",
            Severity.CRITICAL,
            f"{t.item} expired {overdue}d ago (valid {horizon}d)",
            days=overdue,
        )
    remaining = -overdue
    if remaining <= _TRAINING_DUE_SOON_DAYS:
        return Finding(
            "training",
            Severity.WARN,
            f"{t.item} expires in {remaining}d",
            days=-remaining,
        )
    return Finding(
        "training",
        Severity.OK,
        f"{t.item} current; {remaining}d remaining",
        days=-remaining,
    )


def assess_person(p: Person, as_of: Optional[_dt.date] = None) -> HygieneReport:
    """Run the full hygiene assessment for one person."""
    if as_of is None:
        as_of = _dt.date.today()

    findings: list[Finding] = [_assess_investigation(p, as_of)]

    for concern in p.sead4_concerns:
        findings.append(
            Finding(
                "sead4",
                Severity.WARN,
                f"open adjudicative concern: {concern}",
            )
        )

    for r in p.reportables:
        findings.append(_assess_reportable(r, as_of))

    for t in p.trainings:
        findings.append(_assess_training(t, as_of))

    return HygieneReport(p.name, p.eligibility, findings)


def assess_roster(
    people: Iterable[Person], as_of: Optional[_dt.date] = None
) -> list[HygieneReport]:
    return [assess_person(p, as_of) for p in people]
