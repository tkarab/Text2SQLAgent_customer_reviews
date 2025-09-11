# python native packages
from typing_extensions import TypedDict
from typing import Annotated, Any, Dict, Literal, Optional, Sequence, Union

# third party packages
from langchain_community.utilities.sql_database import SQLDatabase, truncate_word
from langgraph.graph.message import add_messages
from sqlalchemy.engine import Result
from sqlalchemy.sql.expression import Executable


class CustomSQLDatabase(SQLDatabase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._usable_tables.union(set(self._inspector.get_materialized_view_names()))
        self._all_tables.union(set(self._inspector.get_materialized_view_names()))

    def run(
        self,
        command: Union[str, Executable],
        fetch: Literal["all", "one", "cursor"] = "all",
        include_columns: bool = False,
        *,
        parameters: Optional[Dict[str, Any]] = None,
        execution_options: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Sequence[Dict[str, Any]], Result[Any]]:
        """Execute a SQL command and return a list of items representing the results.

        If the statement returns rows, a list of the results is returned.
        If the statement returns no rows, an empty list is returned.
        """
        result = self._execute(
            command, fetch, parameters=parameters, execution_options=execution_options
        )

        if fetch == "cursor":
            return result

        res = [
            {
                column: truncate_word(value, length=self._max_string_length)
                for column, value in r.items()
            }
            for r in result
        ]

        if not include_columns:
            res = [tuple(row.values()) for row in res]  # type: ignore[misc]

        if not res:
            return []
        else:
            return res


class State(TypedDict):
    messages: Annotated[list, add_messages]
