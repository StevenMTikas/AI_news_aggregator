BANNER_WIDTH = 80

from .main import (
    DEFAULT_SLUG,
    DEFAULT_TOPIC,
    build_default_inputs,
    run_pipeline,
)


def print_banner(topic: str, timestamp: str, width: int = BANNER_WIDTH) -> None:
    separator = "=" * width
    print(separator)
    print("AI NEWS AGGREGATOR - Blog Post Generator")
    print(separator)
    print(f"Topic: {topic}")
    print(f"Date: {timestamp}")
    print(separator + "\n")


def print_success(output_path) -> None:
    separator = "=" * BANNER_WIDTH
    print("\n" + separator)
    print("SUCCESS: Blog post generated successfully!")
    print("Check the 'output' folder in the root directory for your blog post.")
    print(f"Path: {output_path}")
    print(separator)


def print_error(exc: Exception) -> None:
    separator = "=" * BANNER_WIDTH
    print("\n" + separator)
    print(f"ERROR: {exc}")
    print(separator)


def run(topic: str = DEFAULT_TOPIC, topic_slug: str = DEFAULT_SLUG):
    """
    Run the crew to generate an AI blog post using default CLI behaviour.
    """
    inputs = build_default_inputs(topic, topic_slug)
    print_banner(inputs["topic"], inputs["current_date_and_time"])

    try:
        result, output_path = run_pipeline(inputs)
    except Exception as exc:  # pragma: no cover - CLI friendly output
        print_error(exc)
        raise RuntimeError("An error occurred while running the crew.") from exc

    print_success(output_path)
    return result
