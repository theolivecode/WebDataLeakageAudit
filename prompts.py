QUERY_GENERATION_PROMPT = """You are an expert in using search engines and writing search keywords.
We will breakdown and decompose the user query into {number_of_queries} distinct search queries.
Generate {number_of_queries} distinct search queries that would help gather comprehensive information about this topic.
Each query should focus on a different aspect or perspective.
The queries should be precise, concise, friendly for search engines (not complete sentences), SEO-aware, and relevant to the original query.
Generate queries in the user's native language, do not do any translation.
Return only the queries as a JSON array.

Your response must be a valid JSON array of strings, wrapped with <JSON> and </JSON>.

Example output:
{json_queries_example}

Now, generate the queries based on the user query:
{user_query}"""


LEAKAGE_JUDGE_PROMPT = """You are an expert Data Contamination Auditor.
Your job is to detect if the given text chunk leaks information that originates past the given Information Cutoff Date and how significant this leakage is in answering the given forecasting question.

Question: {question}
Background Info: {background}
Resolution Criteria: {resolution_criteria}
Resolved answer: {resolved_answer}
Information Cutoff Date: {information_cutoff_date}

Post-Cutoff information: Any event, data point, or entity that did not exist or was not public knowledge prior to the Information Cutoff Date.


Judge Process
Step 1:
Scan the text chunk for post-cutoff information, i.e. information that originates after the Information Cutoff Date ({information_cutoff_date}). These can include logical leaks of events/entities that didn't exist pre-cutoff or retroactive revelations where there is a post-cutoff disclosure of previously secret pre-cutoff events.

Step 2:
Score the post-cutoff information given the Leakage Score Rubric below.

Leakage Score Rubric:

0 - Noise (Irrelevant or no post-cutoff information)
Assign 0 if no post-cutoff info exists or post-cutoff info exists but is irrelevant to the question topic and would not change a forecaster's probability estimate at all.

1 - Topical
Assign 1 if the post-cutoff info is related to the question topic but would not help or change a forecaster's answer and reasoning in determining the question's answer.

2 - Weak Signal
Assign 2 if the post-cutoff info is relevant to the question and provides a vague/minor directional signal towards the question's resolution. These are often vague trend statements with little or no quantitative detail.

3 - Major or Partial Direct Signal
Assign 3 if the post-cutoff info provides a major component/signal toward the question's resolution. This could involve having direct/decisive data for a partial component of the question or data from a later date than the desired question date that can be used to strongly infer the resolved answer.


4 - Full Decisive/Direct Leakage
Assign 4 if the post-cutoff info directly reveals the resolved answer whether by explicitly stating it or providing data allowing for a certain logical/mathematical calculation of the answer.

Sometimes what isn't mentioned (absence of information) is important for forecasting. Use absence of information only in clearly comprehensive or high-quality reports that are relevant to the question. Otherwise, score based on what is stated, not omissions. When absence of information is reasonable, it is scored a 3 at most, as we do not want to assume a certain 4.


Example to help anchor scoring:
Ex Question: Will X and Y countries ratify treaty Z by 2024?
Example Cutoff Date: January 15, 2021
'Copyright 2024' is assigned a 0. Irrelevant post-cutoff metadata.
'In 2024, the Treaty Z Secretariat renamed its Working Group 2 to the 'Implementation Committee.'' is assigned a 1. Treaty-adjacent post-cutoff info, but unrelated to whether Country X signed.
'(2023) Country X joined a related initiative that is 'aligned with Treaty Z principles.' is assigned a 2.
'In 2023, Country X's parliament introduced a Treaty Z ratification bill (or a committee opened formal review).' is assigned a 3. Concrete major step toward ratification, strongly informative but not confirmation.
An official, complete 2021-2024 Treaty Z ratification timeline lists Country X ratifying in 2023, which is a 3 for the multi-country question (it decisively answers one component, but not the whole question). The same comprehensive timeline does not list Country Y, which is also a 3 absence-based signal for non-ratification.
The Treaty Z Depositary's official registry (updated 2024) lists Country X ratifying in 2023 and explicitly states Country Y is not eligible to ratify Treaty Z (so no ratification by Y is possible). This is assigned a 4.

Output Format:

Provide your response as a valid JSON object wrapped with <JSON> and </JSON> containing exactly these keys:


<JSON>
{{
  "reasoning": "First, provide all the post-cutoff info found. Then assign a score for each piece of post-cutoff info found based on the Leakage Score Rubric and explain your rationale.",  "contains_post_cutoff_info": boolean,
  "leakage_score": integer (0-4) #Apply the highest leakage score given for the post-cutoff info found here
}}
</JSON>

Text chunk to evaluate:
{context}"""

BINARY_FORECASTING_PROMPT = """You are a professional forecaster interviewing for a job.
The question's forecasting window begins on {open_time}.
Your interview question is:
{title}

Question background:
{background}

This question's outcome will be determined by the specific criteria below. These criteria have not yet been satisfied:
{resolution_criteria}

{fine_print}

Summary Research Report:
Warning: These snippets are from an automated search engine. They may contain irrelevant info, conflicting data, or headlines that do not tell the full story. They may also have ambigious dates. You must evaluate them critically and check specific numbers against the resolution criteria.
{summary_report}

Before answering you write:
(a) The time left from now until the resolution date. Consider the forecasting window of when it began and the resolution date.
(b) The status quo outcome if nothing changed.
(c) A brief description of a scenario that results in a No outcome.
(d) A brief description of a scenario that results in a Yes outcome.

You write your rationale remembering that good forecasters put extra weight on the status quo outcome since the world changes slowly most of the time.

The last thing you write is your final answer. You must write the probability of the "Yes" outcome only. Format it exactly as: "Probability: ZZ%", 0-100"""

