"""
News Agent Module
Handles web searches and news aggregation tasks
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import json
import aiohttp
from dataclasses import dataclass, asdict
import time


@dataclass
class SearchTask:
    """Represents a single search task"""
    query: str
    timestamp: str
    status: str = "pending"
    articles: List[Dict] = None
    
    def __post_init__(self):
        if self.articles is None:
            self.articles = []


class NewsAgent:
    """
    AI News Aggregator Agent
    Performs web searches for AI news and analyzes impact on everyday life
    """
    
    def __init__(self, name: str = "NewsAgent"):
        self.name = name
        self.search_history: List[SearchTask] = []
        
    async def search_web(self, query: str) -> Dict:
        """
        Perform a web search for the given query
        
        Args:
            query: Search query string
            
        Returns:
            Dictionary containing search results with timestamp
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"[{timestamp}] {self.name}: Searching for '{query}'...")
        
        # Simulate web search with mock data
        # In a real implementation, this would use an actual search API
        articles = await self._mock_search(query)
        
        result = {
            'query': query,
            'timestamp': timestamp,
            'status': 'completed',
            'articles': articles
        }
        
        # Add small delay to simulate real search
        await asyncio.sleep(0.5)
        
        print(f"[{timestamp}] {self.name}: Found {len(articles)} articles")
        
        return result
    
    async def _mock_search(self, query: str) -> List[Dict]:
        """
        Mock search function that simulates web search results
        Replace this with actual API calls in production
        
        Args:
            query: Search query string
            
        Returns:
            List of article dictionaries
        """
        # Mock data representing current AI news
        mock_articles = [
            {
                'title': 'AI-Powered Smart Home Devices Transform Daily Living in 2025',
                'url': 'https://example.com/ai-smart-home-2025',
                'snippet': 'New AI assistants are revolutionizing how people manage their homes, from automated climate control to predictive maintenance systems.',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'relevance': 'high'
            },
            {
                'title': 'Healthcare AI: Personal Health Monitoring Becomes Mainstream',
                'url': 'https://example.com/ai-healthcare-monitoring',
                'snippet': 'AI-driven health apps now provide real-time analysis of vital signs, helping millions prevent serious health issues before they develop.',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'relevance': 'high'
            },
            {
                'title': 'AI in Education: Personalized Learning Paths Show Remarkable Results',
                'url': 'https://example.com/ai-education-2025',
                'snippet': 'Students using AI-powered tutoring systems show 40% improvement in learning outcomes, according to recent studies.',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'relevance': 'medium'
            },
            {
                'title': 'Workplace Productivity Soars with AI Assistants',
                'url': 'https://example.com/ai-workplace-productivity',
                'snippet': 'Companies report significant efficiency gains as AI tools handle routine tasks, allowing employees to focus on creative work.',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'relevance': 'high'
            },
            {
                'title': 'AI-Powered Transportation: Self-Driving Features in Everyday Vehicles',
                'url': 'https://example.com/ai-transportation-2025',
                'snippet': 'Advanced driver assistance systems powered by AI are now standard in most new vehicles, reducing accidents by 30%.',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'relevance': 'medium'
            }
        ]
        
        # Return a subset based on query keywords
        return mock_articles[:3]  # Return top 3 results per search
    
    async def execute_searches(self, queries: List[str]) -> List[Dict]:
        """
        Execute multiple search tasks concurrently
        
        Args:
            queries: List of search query strings
            
        Returns:
            List of search results
        """
        print(f"\n{self.name}: Starting {len(queries)} concurrent searches...")
        print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Create tasks for concurrent execution
        tasks = [self.search_web(query) for query in queries]
        
        # Execute all searches concurrently
        results = await asyncio.gather(*tasks)
        
        # Store in history
        self.search_history.extend(results)
        
        return results
    
    def save_results(self, results: List[Dict], filename: str):
        """
        Save search results to a JSON file
        
        Args:
            results: List of search results
            filename: Output filename
        """
        output_data = {
            'agent_name': self.name,
            'total_searches': len(results),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'searches': results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n{self.name}: Results saved to {filename}")
    
    def get_summary(self) -> Dict:
        """
        Get a summary of all searches performed
        
        Returns:
            Dictionary containing search statistics
        """
        total_articles = sum(len(search['articles']) for search in self.search_history)
        
        return {
            'agent_name': self.name,
            'total_searches': len(self.search_history),
            'total_articles_found': total_articles,
            'last_search': self.search_history[-1]['timestamp'] if self.search_history else None
        }

