import os
import json
import traceback
import numpy as np
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import make_pipeline

from prompts import TREND_PLOT_GEN


# Load API key from .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class Eval_Query_Result(BaseModel):
    first_column_is_time_related: bool
    second_column_is_time_related: bool
    first_column_title: str
    second_column_title: str

eval_prompt = ChatPromptTemplate.from_template(TREND_PLOT_GEN)
eval_model = eval_prompt | ChatOpenAI(model="gpt-4o", temperature=0).with_structured_output(Eval_Query_Result)

def check_if_columns_related_to_time(data):
    """
    Calls the LLM to evaluate if the columns' values are time-related.
    """
    try:
        response = eval_model.invoke({"data": data})
        return response
    except Exception as e:
        print("Error generating evaluation response:", e)
        traceback.print_exc()
        return Eval_Query_Result(
            first_column_is_time_related = False,
            second_column_is_time_related = False,
            first_column_title = "",
            second_column_title = ""
        )


def curve_finder(x, y):
    x = np.array(x)
    y = np.array(y)

    model = make_pipeline(StandardScaler(), PolynomialFeatures(), LinearRegression())

    parms = {'polynomialfeatures__degree': np.arange(3, 5)}

    gscv = GridSearchCV(model, parms, cv = 4, scoring='neg_mean_squared_error')
    gscv.fit(x.reshape(-1,1),y)

    space = np.linspace(x.min(),x.max(),101).reshape(-1,1)

    est_deg= gscv.best_params_['polynomialfeatures__degree']

    return space, gscv.predict(space)


def plot_points_and_spline(x_key, x_values, y_key, y_values):
    # Determine the type of x_values and convert if necessary.
    if isinstance(x_values[0], datetime):
        x_values_numeric = mdates.date2num(x_values)
        is_datetime = True
        tick_labels = None
    elif isinstance(x_values[0], (int, float)):
        x_values_numeric = x_values
        is_datetime = False
        tick_labels = None
    else:
        # Assume categorical (e.g. month names). Map them to numeric positions.
        x_values_numeric = list(range(len(x_values)))
        is_datetime = False
        tick_labels = x_values

    # Create the scatter plot for the data points.
    plt.scatter(np.asarray(x_values_numeric, float), y_values, color='red', label='Data Points')

    x_curve, y_curve = curve_finder(x_values_numeric, y_values)
    plt.plot(np.asarray(x_curve, float), y_curve, color='blue', label='Trend line')

    # Format the x-axis for datetime or categorical labels.
    if is_datetime:
        plt.gca().xaxis_date()
        plt.gcf().autofmt_xdate()
    elif tick_labels is not None:
        plt.xticks(np.asarray(x_values_numeric, float), tick_labels)

    plt.xlabel(x_key)
    plt.ylabel(y_key)
    plt.xticks(rotation=35) 
    plt.legend()
    plt.tight_layout()

    plt.savefig(f"trend_analysis_plot.png", bbox_inches='tight')
    plt.close()


def trend_analysis_plot(query_results_list):
    if query_results_list:  # NON zero rows check
        # Failsafe added
        # query_results_list should be a list of dicts
        if not query_results_list or not isinstance(query_results_list, list):
            print("Empty or invalid result format. Skipping plot.")
            return False

        first_row = query_results_list[0]
        keys = list(first_row.keys())
        if len(keys) == 2 and len(query_results_list)>4:  # ONLY two columns for 2D plot
            # Take the first data values and check if only one is time related
            response = check_if_columns_related_to_time(query_results_list[:3])

            # Only one column should have time related values
            if response.first_column_is_time_related != response.second_column_is_time_related:
                # Choose the time-related column for x axis
                if response.first_column_is_time_related == True:
                    x_key, y_key = keys[0], keys[1]
                else:
                    x_key, y_key = keys[1], keys[0]

                x_values = [d[x_key] for d in query_results_list]
                y_values = [d[y_key] for d in query_results_list]
                # Plot data
                plot_points_and_spline(x_key, x_values, y_key, y_values)
                return True

        elif len(keys) == 3 and len(query_results_list)>4:
            if "year" in keys:
                # year_values = {row["year"] for row in query_results_list}
                keys = [k for k in keys if k != "year"]
                query_results_list_no_year = [{key:value for key,value in result.items() if key in keys} for result in query_results_list]
                response = check_if_columns_related_to_time(query_results_list_no_year[:3])

                # Only one column should have time related values
                if response.first_column_is_time_related != response.second_column_is_time_related:
                    # Choose the time-related column for x axis
                    if response.first_column_is_time_related == True:
                        x_key, y_key = keys[0], keys[1]
                    else:
                        x_key, y_key = keys[1], keys[0]

                    x_values = [f"{d['year']}-{d[x_key]}" for d in query_results_list]
                    y_values = [d[y_key] for d in query_results_list]

                    # Plot data
                    plot_points_and_spline(x_key, x_values, y_key, y_values)
                    return True


            else:
                # Case not handled for now
                return False


    # Data NOT plotted
    return False


def main():
    # Example 1: Two-column dataset with categorical (non-time) data.
    # Using month names (as strings) for 12 datapoints.
    data_time_no_time = [
        {'month': 'January',   'sales': 100},
        {'month': 'February',  'sales': 130},
        {'month': 'March',     'sales': 110},
        {'month': 'April',     'sales': 180},
        {'month': 'May',       'sales': 170},
        {'month': 'June',      'sales': 220},
        {'month': 'July',      'sales': 210},
        {'month': 'August',    'sales': 290},
        {'month': 'September', 'sales': 260},
        {'month': 'October',   'sales': 320},
        {'month': 'November',  'sales': 310},
        {'month': 'December',  'sales': 400}
    ]

    # Example 2: Two-column dataset with date strings in the first column.
    data_time_time = [
        {"start_date": "2021-01-01", "end_date": "2021-01-02"},
        {"start_date": "2021-01-03", "end_date": "2021-01-04"},
        {"start_date": "2021-01-05", "end_date": "2021-01-06"},
        {"start_date": "2021-01-07", "end_date": "2021-01-08"},
        {"start_date": "2021-01-09", "end_date": "2021-01-10"},
        {"start_date": "2021-01-11", "end_date": "2021-01-12"}
    ]

    # Example 3: Two-column dataset with non-time data (no time information).
    data_no_time_no_time = [
        {'product': 'Apple',      'price': 1.0},
        {'product': 'Banana',     'price': 0.5},
        {'product': 'Cherry',     'price': 2.0},
        {'product': 'Date',       'price': 3.0},
        {'product': 'Elderberry', 'price': 1.5},
        {'product': 'Fig',        'price': 2.5},
        {'product': 'Grapes',     'price': 2.2}
    ]

    # Example 4: Two-column dataset where one column holds date strings (named "date")
    # even though its name doesn't explicitly indicate time.
    data_no_time_time = [
        {"date": "2021-06-01", "value": 15},
        {"date": "2021-06-02", "value": 18},
        {"date": "2021-06-03", "value": 22},
        {"date": "2021-06-04", "value": 19},
        {"date": "2021-06-05", "value": 30},
        {"date": "2021-06-06", "value": 27},
        {"date": "2021-06-07", "value": 35}
    ]

    # Example 5: Zero rows dataset.
    data_zero_rows = []

    # Example 6: More than two columns (three columns: date, sales, and profit).
    data_more_than_two_columns = [
        {"date": "2021-07-01", "sales": 100, "profit": 30},
        {"date": "2021-07-02", "sales": 140, "profit": 45},
        {"date": "2021-07-03", "sales": 130, "profit": 40},
        {"date": "2021-07-04", "sales": 200, "profit": 60},
        {"date": "2021-07-05", "sales": 180, "profit": 55},
        {"date": "2021-07-06", "sales": 250, "profit": 80}
    ]

    # Example 7: Less than 4 data points.
    data_less_than_two_rows = [
        {"date": "2021-07-01", "sales": 100, "profit": 30},
        {"date": "2021-07-02", "sales": 140, "profit": 45},
    ]

    # Call the plotting function once for each example (without using a loop).
    assert trend_analysis_plot(data_time_no_time) == True
    assert trend_analysis_plot(data_time_time) == False
    assert trend_analysis_plot(data_no_time_no_time) == False
    assert trend_analysis_plot(data_no_time_time) == True
    assert trend_analysis_plot(data_zero_rows) == False
    assert trend_analysis_plot(data_more_than_two_columns) == False
    assert trend_analysis_plot(data_less_than_two_rows) == False

if __name__ == "__main__":
    main()