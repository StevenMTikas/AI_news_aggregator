# AI News Aggregator

An intelligent agent-based system that performs web searches to find current news about AI and its impact on everyday life.

## Features

- **Automated News Search**: Performs 5 concurrent web searches for AI-related news
- **Timestamp Tracking**: All searches include precise timestamps (date and time)
- **Focus on Everyday Impact**: Specifically searches for how AI affects daily life
- **Async Architecture**: Uses Python's asyncio for efficient concurrent searches
- **JSON Export**: Saves all results with timestamps to JSON files

## Project Structure

```
AI_news_aggregator/
├── main.py              # Main entry point
├── news_agent.py        # NewsAgent class and SearchTask logic
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Installation

1. Create a virtual environment (if not already created):
```bash
python -m venv .venv
```

2. Activate the virtual environment:
```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the news aggregator:

```bash
python main.py
```

The agent will:
1. Perform 5 web searches with different queries about AI and everyday life
2. Display results in the console with timestamps
3. Save all results to a JSON file with the current date/time in the filename

## Search Queries

The agent searches for:
1. Latest AI technology in everyday life (2025)
2. Artificial intelligence consumer applications
3. AI impact on daily routines and home automation
4. AI in healthcare and personal assistants
5. AI in education and workplace productivity

## Output

Results are saved to: `ai_news_results_YYYYMMDD_HHMMSS.json`

Each search result includes:
- Query used
- Exact timestamp (YYYY-MM-DD HH:MM:SS)
- Status (completed/failed)
- List of articles found with titles, URLs, and snippets

## Example Output

```
================================================================================
AI NEWS AGGREGATOR - Current News Search
================================================================================
Search initiated at: 2025-10-10 17:30:45
Number of searches: 5
================================================================================

[2025-10-10 17:30:45] AI News Researcher: Searching for 'latest AI technology everyday life 2025'...
[2025-10-10 17:30:45] AI News Researcher: Found 3 articles
...
```

## Customization

To modify search queries, edit the `search_queries` list in `main.py`:

```python
search_queries = [
    "your custom query here",
    "another query",
    # Add more queries...
]
```

## Future Enhancements

- Integration with real search APIs (Google Custom Search, Bing, etc.)
- Natural language processing for article analysis
- Sentiment analysis of AI news
- Trend detection across multiple searches
- Email notifications for important news

## License

MIT License

