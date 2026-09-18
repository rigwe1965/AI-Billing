import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.department import Department
from app.models.provider import Provider, ProviderCode


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def anthropic_provider(db_session):
    provider = Provider(name="Anthropic", code=ProviderCode.anthropic, connector_type="anthropic")
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


@pytest.fixture()
def engineering_dept(db_session):
    dept = Department(name="Engineering", code="ENG")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept
