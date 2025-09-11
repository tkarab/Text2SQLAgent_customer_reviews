import csv
import yaml
from langchain_core.messages.ai import AIMessage

def export_dicts_to_csv(data, file_path):
    """
    Exports a list of dictionaries to a CSV file.

    Parameters:
    data (list of dict): List of dictionaries to export.
    file_path (str): Path to the output CSV file.

    The function writes the keys as the header row,
    followed by the values for each dictionary.
    """
    if not data:
        raise ValueError(
            "The data list is empty. Provide at least one dictionary."
        )

    # Extract keys from the first dictionary
    # (assumes all dictionaries have the same keys)
    headers = data[0].keys()

    # Write to CSV
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # Write header
        writer.writeheader()

        # Write rows
        writer.writerows(data)


def read_include_tables(filename):
    # Load the tables to include
    with open(filename, 'r') as file:
        result = yaml.safe_load(file)
        include_tables = result['include_tables']
        schema = result['schema']
    return include_tables, schema

def extract_sql_query(data):
    try:
        for message in reversed(data['messages']):
            if isinstance(message, AIMessage):
                if hasattr(message, 'tool_calls'):
                    for tool_call in message.tool_calls:
                        if tool_call['name'] == 'sql_db_query' and 'args' in tool_call:
                            query = tool_call['args'].get('query', None)
                            if query:
                                return query
        return None

    except Exception as e:
        print(f"Exception: {e}") 
        return None  # No query generated or extraction failed
