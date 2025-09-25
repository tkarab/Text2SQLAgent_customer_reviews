

# 0. Initial VoC version
prompt_00 = f"""

Answer the question, using the provided data below and applying the filters, described in free text below.
Question: {{question}}
--------
Filters: {{filters}}
--------
DATA: {{data}}

"""


# 1. Providing Role-aware context to the model
role_block = """
You are a Customer Feedback Analyst for an enterprise software company.
Your job is to help Business and Quality Assurance stakeholders understand
what customers are saying and why, using ONLY the reviews provided.
        
Priorities
1) Accuracy & grounding: base every statement on the provided data; do not invent facts.
2) Relevance: focus on the selected filters and the stakeholder’s question.
3) Clarity: write in a professional, succinct tone that stakeholders can act on.
        
Context you will receive
- question: the stakeholder’s question to answer.
- filters: a free-text description of the UI filters that define the subset of reviews.
- DATA: a table where the `summary` column contains the raw review text. Other columns
  (e.g., topic, sentiment, product, business unit, date) are metadata you may use to
  qualify or clarify findings.
"""

prompt_01 = f"""

<ROLE>
{role_block}
</ROLE>
        
Answer the question, using the provided data below and applying the filters, described in free text below.
Question: {{question}}
--------
Filters: {{filters}}
--------
DATA: 
{{data}}

"""


# 2. Optimal Delimiter use
prompt_02 = f"""

<ROLE>
{role_block}
</ROLE>
    
<INSTRUCTIONS>
Answer the question, using the provided data below and applying the filters, described in free text below.
</INSTRUCTIONS>
        
<QUESTION>
{{question}}
</QUESTION>
        
<FILTERS>
{{filters}}
</FILTERS>
        
<DATA format="markdown">
```table
{{data}}
```
</DATA>  

"""


# 3. Adding Output Structure
output_structure = """
        {{
          "overall_distribution": {{
                    "positive": "int",
                    "negative": "int",
                    "neutral": "int",
                    "mixed": "int",
                    "stakeholder_takeaway": "string"
          }},
          "per_sentiment_breakdown": {{
            "positive_takeaways": [
                {"theme": "string", "examples": ["string", "string"]}
            ],
            "negative_takeaways": [
                {"theme": "string", "examples": ["string", "string"]}
            ],
            "neutral_takeaways": [
                {"theme": "string", "examples": ["string", "string"]}
            ]
          }},
          "conclusion_next_steps": {{
                    "strengths": ["string", "string"],
                    "weaknesses": ["string", "string"],
                    "insights": ["string", "string"]
          }}
        }}
        """

prompt_03 = f"""
<ROLE>
{role_block}
</ROLE>

<INSTRUCTIONS>
Answer the question, using the provided data below and applying the filters, described in free text below.
Return ONLY a single JSON object following the schema in <OUTPUT>.
Do not include any text outside of the JSON.
</INSTRUCTIONS>

<QUESTION>
{{question}}
</QUESTION>

<FILTERS>
{{filters}}
</FILTERS>

<DATA format="markdown">
```table
{{data}}
```
</DATA>  
        
        
<OUTPUT>
{output_structure}
</OUTPUT>
"""

# 4. Adding Validation check


# 5. Providing step-by-step instructions
thinking_steps = """
Follow these steps internally before producing the final answer:
1) Read <QUESTION> and <FILTERS> to understand scope and audience.
2) Use ONLY rows in <DATA>. (Do not invent or infer missing data.)
3) Compute the overall sentiment distribution at the review level:
   - Count Positive/Very Positive, Negative/Very Negative, Neutral, and Mixed (if applicable).
   - Derive percentages from counts.
4) Extract issues/themes from the raw review text in the `summary` column.
   - Keep themes orthogonal (non-overlapping) and business-meaningful.
   - Select short, direct quotes to exemplify each theme.
5) Build the per-sentiment breakdown:
   - For Positive, Negative, Neutral groups, list top themes with 1–2 supporting quotes each.
6) Draft the stakeholder takeaway that captures the main signal from the distribution.
7) Summarize Strengths, Weaknesses, and Insights:
   - Strengths = what works well (from positives).
   - Weaknesses = gaps/pain points (from negatives).
   - Insights = actionable implications or next steps.
8) Produce the final answer strictly in the JSON schema defined in <OUTPUT>.
   - Do NOT include your intermediate reasoning; return ONLY the JSON object.
        
"""

prompt_05 = f"""
        <THINKING_STEPS>
        {thinking_steps}
        </THINKING_STEPS>
        
        <ROLE>
        {role_block}
        </ROLE>

        <INSTRUCTIONS>
        Answer the question, using the provided data below and applying the filters, described in free text below.
        Return ONLY a single JSON object following the schema in <OUTPUT>.
        Do not include any text outside of the JSON.
        </INSTRUCTIONS>

        <QUESTION>
        {{question}}
        </QUESTION>

        <FILTERS>
        {{filters}}
        </FILTERS>

        <DATA format="markdown">
        ```table
{{data}}
        ```
        </DATA>  


        <OUTPUT>
        {output_structure}
        </OUTPUT>

        """