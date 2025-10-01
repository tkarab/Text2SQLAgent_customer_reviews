import os
from textwrap import dedent
from google.genai.client import Client
import pandas as pd
from pathlib import Path
import re
import json

from VoC_RCA_Prompt_iterations import prompt_template_00, prompt_template_01, prompt_template_02, prompt_template_03, prompt_template_04, prompt_template_05

file_path = os.path.abspath(__file__)
src_folder = os.path.dirname(file_path)
config_folder = os.path.join(src_folder, 'config')
data_folder = os.path.join(src_folder, 'data')



class USE_CASES:
    use_case_1_viseca = "use_case_1_viseca"
    use_case_2_SLES_for_SAP = "use_case_2_SLES_for_SAP"
    use_case_3_CaaS_Documentation = "use_case_3_CaaS_Documentation"
    
def read_text_file(path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()

def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_dict = {
        "account_name" : "Company Name",
        "overall_sentiment" : "Overall (Record) Sentiment",
        "product" : "Product Family",
    }
    return df.rename(columns=rename_dict)

def split_date_column(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """
    Splits a date column into 'day', 'month', 'year' and drops the original.
    """
    df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
    df["day"] = df[date_col].dt.day
    df["month"] = df[date_col].dt.month_name()
    df["year"] = df[date_col].dt.year
    return df.drop(columns=[date_col])


def explode_topic_triplets(df: pd.DataFrame, base: str = "topic", require_all_three: bool = True) -> pd.DataFrame:
    """Explode topic_i triplets into rows; keep all non-topic cols."""
    # detect indices like topic_1, topic_2, ...
    idx_pat = re.compile(rf"^{re.escape(base)}_(\d+)$")
    indices = sorted(
        int(m.group(1))
        for c in df.columns
        for m in [idx_pat.match(c)]
        if m
    )

    # collect all topic-wide columns to exclude from keep
    topic_cols = set()
    for i in indices:
        topic_cols.update({
            f"{base}_{i}",
            f"{base}_{i}_sentiment",
            f"{base}_{i}_parent_topic",
        })

    keep_cols = [c for c in df.columns if c not in topic_cols]

    rows = []
    for _, row in df.iterrows():
        common = {k: row[k] for k in keep_cols}
        for i in indices:
            t   = row.get(f"{base}_{i}")
            s   = row.get(f"{base}_{i}_sentiment")
            par = row.get(f"{base}_{i}_parent_topic")

            ok = (par != "Other") and ((pd.notna(t) and pd.notna(s) and pd.notna(par)) if require_all_three else pd.notna(t))
            if ok:
                rows.append({**common, "Topic": t, "Topic Sentiment": s, "Parent Topic": par})

    return pd.DataFrame(rows, columns=keep_cols + ["Topic", "Topic Sentiment", "Parent Topic"])


def preprocess_df(df: pd.DataFrame) -> pd.DataFrame:
    # 0. reset index
    df = df.reset_index(drop=True)
    # 1. remove unnecessary columns
    df = df.drop(columns=["business_unit", "source", "geo", "account_number"])
    # 2. rename columns
    df = rename_columns(df)
    # 3. reshape 'date' column
    df = split_date_column(df, date_col="date")
    # 4. expand topic columns into rows
    df = explode_topic_triplets(df)
    
    return df

def print_sentiment_counts(df):
    sentiment_levels = ["Very negative", "Negative", "Mixed", "Positive", "Very positive"]

    # ensure categorical with all 5 levels
    df["Topic Sentiment"] = pd.Categorical(df["Topic Sentiment"], categories=sentiment_levels, ordered=True)

    # topics × sentiment counts with all columns present
    sentiment_pivot = (
        df.groupby(["Topic", "Topic Sentiment"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=sentiment_levels, fill_value=0)
    )

    # add total mentions
    sentiment_pivot["Total_mentions"] = sentiment_pivot.sum(axis=1)

    # optional: bring Topic back as a column
    result = sentiment_pivot.reset_index()

    print("Sentiment counts:")
    print(result.to_markdown())

    return

def parse_gemini_response_to_json(response_text: str) -> dict:
    """
    Extract a JSON object from Gemini response text.
    Handles ```json fences and leading/trailing noise.
    """
    t = response_text.strip()

    # Strip code fences if present
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n```$", "", t, flags=re.DOTALL)

    # Trim whitespace
    t = t.strip()

    # Try direct JSON first
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # Fallback: grab the first {...} block (greedy) and parse
    m = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
    if m:
        candidate = m.group(0)
        # try again
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse JSON from Gemini response.")

def format_dashboard_text(data: dict) -> str:
    """
    Build a readable string for the dashboard.
    Handles missing/malformed fields gracefully.
    Includes key takeaways and examples under each topic.
    If validation.is_rejected is True -> show rejection title + message only.
    Else -> show topics (with key takeaways & examples) and overall strengths/weaknesses.
    """
    def _coerce_bool(x):
        # accept True/False, "true"/"false" (case-insensitive), 1/0
        if isinstance(x, bool):
            return x
        if isinstance(x, (int, float)):
            return bool(x)
        if isinstance(x, str):
            return x.strip().lower() in {"true", "1", "yes"}
        return False

    # ----- Validation gate -----
    validation = data.get("validation") or {}
    is_rejected = _coerce_bool(validation.get("is_rejected"))
    if is_rejected:
        message = validation.get("message") or "Your question was rejected."
        lines = []
        lines.append("### QUESTION REJECTED")
        lines.append(f"Message: '{message.strip()}'")
        return "\n".join(lines).strip()


    lines = []
    lines.append("### TOPIC-LEVEL DISTRIBUTION AND INSIGHTS")

    topics = data.get("topics") or []
    if isinstance(topics, list):
        for t in topics:
            if not isinstance(t, dict):
                continue
            title = str(t.get("topic", "Untitled topic")).strip() or "Untitled topic"
            takes = t.get("takeaways") or []
            examples = t.get("examples") or []

            lines.append(f"--- Topic: {title} ---")

            # Key takeaways
            if isinstance(takes, list) and takes:
                lines.append("  Key takeaways:")
                for k in takes:
                    if k:
                        lines.append(f"    • {str(k)}")
            else:
                lines.append("  Key takeaways: -")

            # Examples
            if isinstance(examples, list) and examples:
                lines.append("  Examples:")
                for ex in examples:
                    if ex:
                        lines.append(f"    → \"{str(ex)}\"")
            else:
                lines.append("  Examples: -")

            lines.append("")  # blank line between topics
    else:
        lines.append("No topics found.\n")

    overall = data.get("overall_strengths_and_weaknesses") or {}
    if not isinstance(overall, dict):
        overall = {}

    strengths = overall.get("overall_strengths") or []
    weaknesses = overall.get("overall_weaknesses") or []

    lines.append("### OVERALL STRENGTHS AND WEAKNESSES")

    if isinstance(strengths, list) and strengths:
        lines.append("  Strengths:")
        for s in strengths:
            lines.append(f"    • {str(s)}")
    else:
        lines.append("  Strengths: -")

    if isinstance(weaknesses, list) and weaknesses:
        lines.append("  Weaknesses:")
        for w in weaknesses:
            lines.append(f"    • {str(w)}")
    else:
        lines.append("  Weaknesses: -")

    return "\n".join(lines).strip()

def build_prompt(
    template: str,
    data_df: pd.DataFrame,
    filters: str,
    question: str,
    data_format: str = "markdown",  # "markdown" | "html"
) -> str:
    if data_format == "markdown":
        data_str = data_df.to_markdown(index=False)
    elif data_format == "html":
        data_str = data_df.to_html(index=False)
    else:
        raise ValueError("data_format must be 'markdown' or 'html'")

    filled = template.format(
        data=data_str,
        filters=filters,
        question=question,
    )
    return dedent(filled).strip()

# ------------------------ MAIN ------------------------

model_name = 'gemini-2.5-pro'
credentials_path = os.path.join(config_folder, 'vertex.json')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

client = Client(
    vertexai=True,
    project="voice-of-customer-ai-194353",
    location="us-central1"
)

use_case = USE_CASES.use_case_1_viseca
data_path = os.path.join(data_folder, use_case)

df        = pd.read_csv(os.path.join(data_path,'data.csv'), index_col=0)
# df = df.iloc[:min(len(df), 3), :]
df = preprocess_df(df)
print_sentiment_counts(df)
question_str  = read_text_file(os.path.join(data_path, 'user_question.txt'))
filters_str   = read_text_file(os.path.join(data_path, 'filters.txt'))

irrelevant_q1 = "What has the stock market been like the past week in Europe?"
irrelevant_q2 = "Best laptops available under 1000$"
irrelevant_q3 = "Can I have a summary of the reviews of the 'Rancher Prime' product"
irrelevant_q4 = "Please analyze the customer Feedback from 'Viseca Payment Services SA"

question_str = irrelevant_q4

prompt_initial = build_prompt(
    template=prompt_template_00,
    data_df=df,
    data_format="html",
    question=question_str,
    filters=filters_str
)
prompt_updated = build_prompt(
    template=prompt_template_05,
    data_df=df,
    data_format = "markdown",
    question=question_str,
    filters=filters_str
)

# print(f"INITIAL PROMPT: \n\n{prompt_initial}")
# print(f"IMPROVED PROMPT: \n\n{prompt_updated}")

# response_init_prompt = client.models.generate_content(
#             model=model_name,
#             contents=prompt_initial
# )
#
# print(f"RESPONSE WITH INITIAL PROMPT:")
# print(response_init_prompt.text)

response_updated_prompt = client.models.generate_content(
            model=model_name,
            contents=prompt_updated,
)

response_json = parse_gemini_response_to_json(response_text=response_updated_prompt.text)
dashboard_text = format_dashboard_text(data=response_json)


print(f"\n\nRESPONSE WITH UPDATED PROMPT:")
print(dashboard_text)
print()






