"""CLI entrypoint for local dev (``python -m interview_simulator.engineering.main``)."""

from __future__ import annotations


def main() -> None:
    import uvicorn

    from interview_simulator.engineering.logging_setup import configure_logging
    from interview_simulator.model_layer.chains import load_dotenv_if_present

    load_dotenv_if_present()
    configure_logging()

    uvicorn.run(
        "interview_simulator.engineering.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
