def main() -> None:
    """Entry point for `uv run trishul-api`: development server with auto-reload."""
    import uvicorn

    uvicorn.run("trishul_api.main:create_app", factory=True, host="127.0.0.1", port=8000, reload=True)
