"""
AI News Aggregator Agent
Performs web searches for current AI news and analyzes impact on everyday life
"""

import asyncio
from datetime import datetime
from typing import List, Dict
import json
from news_agent import NewsAgent


async def main():
    """Main function to run the AI news aggregator"""

    # Initialize the news agent
    agent = NewsAgent(name="AI News Researcher")

    # Define search queries focused on AI's impact on everyday life
    search_queries = [
        "latest AI technology everyday life 2025",
        "artificial intelligence consumer applications October 2025",
        "AI impact daily routine home automation 2025",
        "AI healthcare personal assistant news 2025",
        "AI education workplace productivity 2025"
    ]

    # Create search tasks
    print("=" * 80)
    print("AI NEWS AGGREGATOR - Current News Search")
    print("=" * 80)
    print(f"Search initiated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Number of searches: {len(search_queries)}")
    print("=" * 80)
    print()

    # Execute all searches
    results = await agent.execute_searches(search_queries)

    # Display results
    print("\n" + "=" * 80)
    print("SEARCH RESULTS SUMMARY")
    print("=" * 80)

    for i, result in enumerate(results, 1):
        print(f"\n{'─' * 80}")
        print(f"SEARCH #{i}")
        print(f"{'─' * 80}")
        print(f"Query: {result['query']}")
        print(f"Timestamp: {result['timestamp']}")
        print(f"Status: {result['status']}")
        print(f"Articles Found: {len(result['articles'])}")
        print()

        if result['articles']:
            print("Top Articles:")
            for j, article in enumerate(result['articles'], 1):
                print(f"\n  {j}. {article['title']}")
                print(f"     URL: {article['url']}")
                if article['snippet']:
                    print(f"     Preview: {article['snippet'][:150]}...")
        else:
            print("  No articles found for this query.")

    # Save results to file
    output_file = f"ai_news_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    agent.save_results(results, output_file)
    print(f"\n{'=' * 80}")
    print(f"Results saved to: {output_file}")
    print(f"Total searches completed: {len(results)}")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

