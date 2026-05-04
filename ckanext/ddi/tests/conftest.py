import pytest
from ckan.plugins import toolkit


@pytest.fixture(autouse=True)
def load_standard_plugins(with_plugins):
    """Ensure plugins from ckan.plugins are loaded for every test."""
    pass


@pytest.fixture
def clean_db(reset_db, migrate_db_for):
    reset_db()
    if toolkit.check_ckan_version(min_version="2.11"):
        migrate_db_for("harvest")
