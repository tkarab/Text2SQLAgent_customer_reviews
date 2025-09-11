# python native packages
import os
from dotenv import load_dotenv

# third party packages
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, StateGraph
from langchain_core.messages.tool import ToolMessage

# custom packages
from prompts import QUERY_GEN_SYSTEM
from models import CustomSQLDatabase, State
from utils import export_dicts_to_csv, read_include_tables, extract_sql_query
from trend_analysis import trend_analysis_plot
load_dotenv()

db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

include_tables_yaml_filepath = os.getenv("INCLUDE_TABLES_YAML_FILEPATH", 'agent/src/config.yaml')
include_tables, schema = read_include_tables(include_tables_yaml_filepath)

# Connection to Postgresql db
db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
db = CustomSQLDatabase.from_uri(
    db_url, 
    view_support=True, 
    include_tables=include_tables if include_tables else None,
    schema=schema
    )

# SQL Manipulation Tools
toolkit = SQLDatabaseToolkit(db=db, llm=ChatOpenAI(model="gpt-4o"))
sql_db_toolkit_tools = toolkit.get_tools()

query_gen_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", QUERY_GEN_SYSTEM),
        MessagesPlaceholder(variable_name="messages"),
    ]
)
query_gen_model = query_gen_prompt | ChatOpenAI(
    model="gpt-4o", temperature=0
).bind_tools(tools=sql_db_toolkit_tools)

graph_builder = StateGraph(State)


def query_gen_node(state: State):
    last_message = state["messages"][-1]

    # SQL query results limiter
    if isinstance(last_message, ToolMessage):
        if last_message.name == "sql_db_query":
            # The sql_db_query tool was called right before
            query = extract_sql_query(state)
            if query:
                print(f"Query: {query}")
                query_results_list = db.run_no_throw(query, include_columns=True)

                # trend_analysis_plot(query_results_list)

                items_threshold = 5  # Max number of items to consider
                if len(query_results_list) > items_threshold:
                    # Store query results in csv
                    export_dicts_to_csv(query_results_list, "query_results.csv")

                    # Limit the content passed to the LLM
                    updated_content = str(query_results_list[:items_threshold])
                    updated_content += \
                        "\nInform the user that only the first {items_threshold}\
                        results are displayed and also note that the complete results\
                        are exported automatically in the \"query_result.csv\" file.\n"
                    state["messages"][-1].content = updated_content
    message = query_gen_model.invoke(state["messages"])

    return {"messages": [message]}


graph_builder.add_node("query_gen", query_gen_node)
query_gen_tools_node = ToolNode(tools=sql_db_toolkit_tools)
graph_builder.add_node("query_gen_tools", query_gen_tools_node)

graph_builder.add_conditional_edges(
    "query_gen",
    tools_condition,
    {"tools": "query_gen_tools", END: END},
)

graph_builder.add_edge("query_gen_tools", "query_gen")
graph_builder.set_entry_point("query_gen")
graph = graph_builder.compile()

QUESTION = "i want all reviews from Equinix LLC"

inputs = {"messages": [{"role": "user", "content": QUESTION}]}
answer = graph.invoke(inputs)
print(f"Q: {QUESTION}")
print(f"A: {answer['messages'][-1].content}")

# Exported for external use
__all__ = ["graph"]

