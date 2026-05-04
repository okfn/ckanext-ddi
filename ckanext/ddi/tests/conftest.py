import pytest


@pytest.fixture(autouse=True)
def load_standard_plugins(with_plugins):
    """Ensure plugins from ckan.plugins are loaded for every test."""
    pass


@pytest.fixture
def clean_db(reset_db, migrate_db_for):
    reset_db()
    migrate_db_for("harvest")
