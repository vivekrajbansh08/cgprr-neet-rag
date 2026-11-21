# Blind questions: results

The five questions in `eval/blind/questions.txt` came from a person not involved in the project.
They were committed on their own in commit `725dcd8` before any of them was run. Each English
version was then sent exactly once to `POST http://127.0.0.1:8002/ask` with body
`{"question": ..., "debug": true}`, on 2026-11-21, with no code or configuration changes before or after.
The answer service ran at commit `725dcd8` with model qwen2.5:7b-instruct (Q4_K_M) on Ollama
0.40.16.

Verdicts use one of: correct with citation, correct refusal, correct clarify, wrong, unhelpful.

None of the five replies contained a figure, so there was no number to check. Postgres was checked
as `neet_reader` for whether the asked-about information exists at all: the `neet` schema has no
fee or bond column, and none of the 8,410 indexed text chunks mentions "fee", "bond" or "category
rank". "Domicile" appears only inside quota names on allotment rows.

## 1

- Original: "At what rank which college can we get?"
- English: "At what rank can we get which college?"
- Status: clarify (no citations, 1 LLM call, 1.95 s)

```
Which institute do you mean? I answer from per-institute closing ranks, so please name the college (and its city), plus the quota, category and round if you know them.
```

Citations: none.

Verdict: unhelpful. The question asks which colleges are within reach at a given rank, which is
what the college predictor does. The reply asks the person to name a college, the very thing they
want to find, and does not mention the predictor or ask for their rank. No wrong figure was given.

## 2

- Original: "What is the category rank?"
- English: "What is the category rank?"
- Status: clarify (no citations, 1 LLM call, 1.83 s)

```
Which institute do you mean? I answer from per-institute closing ranks, so please name the college (and its city), plus the quota, category and round if you know them.
```

Citations: none.

Verdict: unhelpful. The question most likely asks what a category rank is. The system read it as a
closing-rank lookup and asked for an institute. It did not explain the term, did not say that MCC
allotment lists are ordered by All India Rank, and did not say that category ranks are not in the
indexed data. No wrong figure was given.

## 3

- Original: "Phir...kaun sa college me bond h?"
- English: "Then, which colleges have a bond?"
- Status: answered (template reply, intent classified as advice; no citations, verifier passed
  with no numbers; 1 LLM call, 1.84 s)

```
I can't make that decision for you, and I give no recommendation either way. What the indexed data can show: past closing ranks from the NEET-UG 2025 MCC counselling rounds, per institute, course, quota (including Deemed/Paid Seats Quota) and allotted category, each with its round and the count of allotments behind it. What it cannot show: fees, costs, college quality, outcomes, or how next counselling will go, so I can't weigh a private college against other options. If you tell me your AIR, category, quota and the colleges you are considering, I can look up their past closing ranks for you.
```

Citations: none.

Verdict: unhelpful. The reply invents nothing and correctly describes what the data covers, but it
answers a decision question that was not asked ("I can't make that decision for you") and never
says that service bonds are not in the data. A reader has to infer that from "costs". It comes close
to a correct refusal but does not give the reason that matters.

## 4

- Original: "Kitna fees h kis college ka?"
- English: "How much are the fees at which college?"
- Status: clarify (no citations, 1 LLM call, 1.99 s)

```
Which institute do you mean? I answer from per-institute closing ranks, so please name the college (and its city), plus the quota, category and round if you know them.
```

Citations: none.

Verdict: unhelpful. Fees are not in the indexed MCC data, so naming a college cannot lead to an
answer. The clarify suggests otherwise and does not say that fees are outside its scope. A refusal
naming fees as not covered would have been correct.

## 5

- Original: "State preference kya h?"
- English: "What is the state preference?"
- Status: clarify (no citations, 1 LLM call, 1.81 s)

```
Which institute do you mean? I answer from per-institute closing ranks, so please name the college (and its city), plus the quota, category and round if you know them.
```

Citations: none.

Verdict: unhelpful. The question asks for the meaning of a counselling term. State preference and
domicile rules belong to state counselling and are not described in the indexed MCC allotment
lists, which only carry quota labels. The reply neither explains the term nor says it is out of
scope.

## Summary

| # | question (English) | status | verdict |
|---|---|---|---|
| 1 | At what rank can we get which college? | clarify | unhelpful |
| 2 | What is the category rank? | clarify | unhelpful |
| 3 | Then, which colleges have a bond? | answered (no figures) | unhelpful |
| 4 | How much are the fees at which college? | clarify | unhelpful |
| 5 | What is the state preference? | clarify | unhelpful |

The system stayed safe on all five unseen questions. It gave no figure, cited nothing it could not
support, made no recommendation, and answered quickly (under 2 s each). Where it fell short was
in helping. Four of the five replies were the same fixed clarify asking for an institute, quota,
category and round, a request that fits a closing-rank lookup but none of these questions. For fees
(question 4) and bonds (question 3) the data holds no answer, yet neither reply said so plainly:
the fee reply invited a follow-up that cannot succeed, and the bond reply described fees and costs
as out of scope without naming bonds. Two questions asked what a term means (category rank, state
preference); the system has no glossary path for definitions, so it answered neither. The question
about which colleges a rank can reach is served by the predictor, but the answer service did not
point to it. Known limits, not fixed here: no route from `/ask` to the predictor, no out-of-scope
refusal naming fees, bonds or state-quota rules, no handling of definition questions, and a clarify
that does not adapt to what is missing.
