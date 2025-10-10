#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from ai_news_aggregator.crew import AiNewsAggregator

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew to generate an AI blog post.
    """
    now = datetime.now()
    inputs = {
        'topic': 'AI and how it impacts everyday life',
        'current_year': str(now.year),
        'current_date_and_time': now.strftime('%Y-%m-%d %H:%M:%S')
    }

    print("=" * 80)
    print("AI NEWS AGGREGATOR - Blog Post Generator")
    print("=" * 80)
    print(f"Topic: {inputs['topic']}")
    print(f"Date: {inputs['current_date_and_time']}")
    print("=" * 80)
    print()

    try:
        result = AiNewsAggregator().crew().kickoff(inputs=inputs)
        print("\n" + "=" * 80)
        print("✅ Blog post generated successfully!")
        print("Check the 'output' folder in the root directory for your blog post.")
        print("=" * 80)
        return result
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ Error: {e}")
        print("=" * 80)
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    try:
        AiNewsAggregator().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        AiNewsAggregator().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }
    
    try:
        AiNewsAggregator().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
