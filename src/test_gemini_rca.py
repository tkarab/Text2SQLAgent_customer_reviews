import os
from textwrap import dedent
from google.genai.client import Client
import pandas as pd
from pathlib import Path
import re
from VoC_RCA_Prompt_iterations import prompt_00, prompt_01, prompt_02

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

            ok = (pd.notna(t) and pd.notna(s) and pd.notna(par)) if require_all_three else pd.notna(t)
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


def build_prompt(
        template: str,
        data: str,
        filters: str,
        question: str
    ) -> str:
    """
    Fill a prompt template with a DataFrame, filters, and a question.
    Placeholders in the template should be:
      {data}     -> replaced with HTML table from the DataFrame
      {filters}  -> replaced with the filters string
      {question} -> replaced with the user question
    """
    filled = template.format(
        data=data,
        filters=filters,
        question=question
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
df = df.iloc[:min(len(df), 3), :]
df = preprocess_df(df)
question_str  = read_text_file(os.path.join(data_path, 'user_question.txt'))
filters_str   = read_text_file(os.path.join(data_path, 'filters.txt'))

prompt_initial = build_prompt(
    template=prompt_00,
    data=df.to_html(),
    question=question_str,
    filters=filters_str
)
prompt_updated = build_prompt(
template=prompt_02,
    data=df.to_markdown(index=False),
    question=question_str,
    filters=filters_str
)

print(f"INITIAL PROMPT: \n\n{prompt_initial}")
print(f"IMPROVED PROMPT: \n\n{prompt_updated}")

response_init_prompt = client.models.generate_content(
            model=model_name,
            contents=prompt_initial
)
response_updated_prompt = client.models.generate_content(
            model=model_name,
            contents=prompt_updated,
)







