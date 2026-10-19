from importlib.metadata import PackageNotFoundError, version


def app_version() -> str:
    """Version of the application: `project.version` of pyproject.toml, which release-please keeps up to date. "unknown"
    when the package is not installed (running from the sources without `uv sync`)."""
    try:
        return version("backend")
    except PackageNotFoundError:
        return "unknown"
