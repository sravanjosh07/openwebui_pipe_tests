import os
from crewai import Agent, Task, Crew, Process
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

from dotenv import load_dotenv
load_dotenv()

server_params = StdioServerParameters(
    command="python",
    args=["/Users/sravanjosh/Documents/agents_mcp/openwebui-clean/rfc/math_server.py"],
    env={**os.environ},
)


# serverparams = {
#     "url": "https://calculator-mcp-server.apps.live-demo.truefoundry.cloud/mcp",
#     "transport": "streamable-http"
# }

prompt = "add two and forty"  

with MCPServerAdapter(server_params) as mcp_tools:
    print("Available tools:", [t.name for t in mcp_tools])

    calc_agent = Agent(
        role="Calculator",
        goal="Use the MCP calculator tool to perform math requested in the task.",
        backstory="Local stdio MCP demo.",
        tools=mcp_tools,
        verbose=True,
    )

    task = Task(
        description=prompt,
        expected_output="Return the computed numeric result (just the number).",  
        agent=calc_agent,
        markdown=True,
    )

    crew = Crew(
        agents=[calc_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff()
    print("Crew result:", result)