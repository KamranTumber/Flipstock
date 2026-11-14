import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEMO_MODE", "false")
os.environ.setdefault("USE_PLAYWRIGHT", "false")


@pytest.fixture(autouse=True)
def memory_db():
    from app import db, models  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    db.set_engine(engine)
    yield engine
    db.set_engine(None)
