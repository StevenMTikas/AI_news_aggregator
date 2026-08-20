from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, output_pydantic, task
from crewai_tools import SerperDevTool

from .schemas import BlogContent as _BlogContent

SERPER_TOOL = SerperDevTool()
BlogContent = output_pydantic(_BlogContent)


@CrewBase
class AiNewsAggregator:
    """AiNewsAggregator crew"""

    agents: List[BaseAgent]
    tasks: List[Task]
    BlogContent = BlogContent

    @agent
    def keyword_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["keyword_researcher"],  # type: ignore[index]
            verbose=True,
            tools=[SERPER_TOOL],
        )

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],  # type: ignore[index]
            verbose=True,
            tools=[SERPER_TOOL],
        )

    @agent
    def blog_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["blog_writer"],  # type: ignore[index]
            verbose=True,
        )

    @task
    def keyword_research_task(self) -> Task:
        return Task(
            config=self.tasks_config["keyword_research_task"],  # type: ignore[index]
        )

    @task
    def research_task(self) -> Task:
        keyword_task = self.keyword_research_task()
        return Task(
            config=self.tasks_config["research_task"],  # type: ignore[index]
            context=[keyword_task],
        )

    @task
    def blog_writer_task(self) -> Task:
        research = self.research_task()
        return Task(
            config=self.tasks_config["blog_writer_task"],  # type: ignore[index]
            context=[research],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the AiNewsAggregator crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
