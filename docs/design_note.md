# NEET.info Counselling Assistant

<p class="subtitle">Design note · AI Developer take-home, CGPRR group · Vivek Rajbansh · 21 November 2026</p>

## What it does

The assistant answers questions about NEET-UG 2025 counselling using the official results published by the Medical Counselling Committee (MCC). Every figure it gives comes with the exact file and page it was taken from, so a reader can check it. When the answer is not in those documents, it says so instead of guessing. It runs entirely on one computer, with no outside service involved.

Source of all data: Medical Counselling Committee (MCC), Government of India, mcc.nic.in.

## How it keeps answers correct

Most counselling questions turn on numbers, such as a closing rank, the last All India Rank that received a seat in a given round. An AI model that recalls or works out such a number can be wrong in a way the reader cannot see. So the system is built so that the model never supplies a number.

- Figures come from a database built from MCC's PDFs, never from the AI model's memory.
- Every figure is checked against the row it cites before it is shown. If the check fails, the answer is withheld.
- Rank comparisons ("Was my rank within the closing rank?") are calculated by the program, not the model.
- Colleges with similar names are never merged. If a name could mean two campuses, the assistant asks which one.

## How it works

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 150" width="100%" font-family="NoteSans, sans-serif" font-size="11" fill="#212224"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><polyline points="0,0 10,5 0,10" fill="none" stroke="#142644" stroke-width="1.4"/></marker></defs><rect x="8" y="8" width="624" height="134" rx="6" fill="#FAFAFA" stroke="#142644" stroke-width="1"/><text x="22" y="28">This computer: nothing leaves it</text><rect x="23" y="50" width="126" height="68" rx="4" fill="#FFFFFF" stroke="#142644" stroke-width="1"/><text x="86" y="80" text-anchor="middle"><tspan x="86">MCC result</tspan><tspan x="86" dy="14">PDFs</tspan></text><rect x="179" y="50" width="126" height="68" rx="4" fill="#FFFFFF" stroke="#142644" stroke-width="1"/><text x="242" y="80" text-anchor="middle"><tspan x="242">Local</tspan><tspan x="242" dy="14">database</tspan></text><rect x="335" y="50" width="126" height="68" rx="4" fill="#FFFFFF" stroke="#142644" stroke-width="1"/><text x="398" y="73" text-anchor="middle"><tspan x="398">Assistant</tspan><tspan x="398" dy="14">(open AI model</tspan><tspan x="398" dy="14">+ checker)</tspan></text><rect x="491" y="50" width="126" height="68" rx="4" fill="#FFFFFF" stroke="#142644" stroke-width="1"/><text x="554" y="80" text-anchor="middle"><tspan x="554">Ask and</tspan><tspan x="554" dy="14">Predictor screens</tspan></text><line x1="149" y1="84" x2="177" y2="84" stroke="#142644" stroke-width="1" marker-end="url(#arrow)"/><line x1="305" y1="84" x2="333" y2="84" stroke="#142644" stroke-width="1" marker-end="url(#arrow)"/><line x1="461" y1="84" x2="489" y2="84" stroke="#142644" stroke-width="1" marker-end="url(#arrow)"/></svg>

MCC's allotment PDFs are read once into a local database, and each row keeps a note of the file, page and line it came from. The Ask screen answers questions in plain language. The Predictor screen takes a rank, category, state and quota and lists colleges whose past closing ranks fit, using fixed rules in the program with no AI model involved.

## What was tested and what it showed

| Test | Result | What it means |
|---|---|---|
| 18 questions written and locked before building | All 18 passed | The same questions were also used while building, so this is not an independent score. |
| 12 new questions not seen before | Found 7 faults, all fixed | The fixes were made for the type of problem, not for the specific question. |
| 5 questions from someone outside the project, run once with no changes | No wrong figures, but none were helpful | It asked for a college name instead of saying that fees, bonds and state quotas are not in MCC's results, and did not point to the Predictor. |
| Figures traced to their source | Spot-checked by hand against the PDFs | Each answer shows the file, page and line it came from, so anyone can repeat the check. |

## Speed and hardware

Tokens are roughly word pieces; the model writes its answers one token at a time.

| | Measured on the laptop (Apple M5, 16 GB) | Estimated on the office GPU (RTX 6000 Ada, 48 GB) |
|---|---|---|
| Average answer that uses the AI model | About 13 seconds | About 2 seconds |
| Slowest answer in the test (same question on both) | About 27.5 seconds | About 3.8 seconds |
| Predictor | Typically under a hundredth of a second | The same; no AI model is involved |
| Text generation speed | About 9 tokens per second | About 125 tokens per second |
| Model size that fits | The 7-billion-parameter model used here | A model of about 32 billion parameters, with room for long questions |

The laptop ran short of memory during the test and fell back on disk, so its slowest times are inflated. Questions the assistant refuses outright, such as those about other years, take a fraction of a second. The GPU figures are estimates worked out from the card's published specifications and stated assumptions, not measurements. The GPU setup is planned and has not been run: the repository holds only a commented-out placeholder for the GPU server, not a working configuration. The laptop figures and the estimates both come from the benchmark record in the repository.

## Models

Qwen2.5 7B Instruct writes the answers and is released under the Apache 2.0 licence. bge-m3 handles search and is released under the MIT licence. I chose them because both have open licences, run offline and fit in 16 GB of memory together with the database. On the office GPU, a larger model of about 32 billion parameters would fit.

## Privacy

Everything runs on one machine. No question, answer or document is sent to any outside service, and an automated test confirms that the web screens make no outside connections. The assistant can only read the data; it cannot change or delete anything. Individual allotment rows stay on the machine, and nothing derived from MCC's files is published, since MCC requires permission to reproduce its material. On a shared office server, each business (NEET.info, Hirrx and the editorial team) would get its own separate database and its own access keys.

## Running cost

There is no charge per question. The only running cost is electricity. A GPU workstation drawing an assumed 450 W, at an assumed ₹8 per unit, costs about ₹3.60 per hour or about ₹29 for an 8-hour day. The tariff is a placeholder and should be replaced with the actual rate.

## Known limits and next steps

- Questions about fees, bonds and state quotas should get a clear "this is not in MCC's data" reply, and "which college can I get?" questions should be sent to the Predictor. Neither happens yet.
- Only 2025 data is loaded, and only Rounds 1 to 3.
- Some institute names still need the user to pick a campus.
- Running the system on the office GPU would replace the estimates above with measurements.

Technical details, setup steps and the full test record are in the repository README.
