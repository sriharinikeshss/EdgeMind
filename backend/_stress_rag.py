import httpx, sys, io, time, uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "http://localhost:8000"

def login(u, p):
    return httpx.post(f"{BASE}/api/auth/login", data={"username": u, "password": p}).json()["access_token"]

admin = login("admin", "kavach123")
H = {"Authorization": f"Bearer {admin}"}

RUN_ID = uuid.uuid4().hex[:6]  # keep this run's docs distinguishable from any prior leftovers

results = []
def check(label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    results.append((status, label, detail))
    print(f"[{status}] {label}" + (f"\n       {detail}" if detail and status == "FAIL" else ""))

# ── Synthetic SOP corpus: 5 distinct, non-overlapping topics ────────────────
SOPS = {
    f"sop_valve_{RUN_ID}.txt": b"""
Standard Operating Procedure: Valve Maintenance (SOP-VM-101)

Section 1: Scope
This procedure covers maintenance of pressure relief valves in Unit 4.

Section 2: Pressure Limits
The maximum allowable operating pressure for Valve V-301 is 175 PSI.
Valve V-302 has a maximum allowable pressure of 220 PSI.
Any reading above these limits requires immediate shutdown and inspection.

Section 3: Inspection Schedule
Valves must be inspected every 90 days by a certified technician.
A full teardown inspection is required annually.

Section 4: Certification
Only technicians holding a Level 2 Valve Certification may perform maintenance.
""",
    f"sop_fire_{RUN_ID}.txt": b"""
Standard Operating Procedure: Fire Safety and Extinguisher Inspection (SOP-FS-205)

Section 1: Extinguisher Types
Class ABC extinguishers must be mounted within 50 feet of any flammable storage area.

Section 2: Inspection Frequency
Fire extinguishers must be visually inspected monthly and pressure-tested every 5 years.
The maximum acceptable pressure gauge reading is in the green zone, between 100 and 175 PSI.

Section 3: Evacuation Procedure
In the event of a fire alarm, all personnel must evacuate via the nearest marked exit
and assemble at Muster Point B within 5 minutes.

Section 4: Reporting
Any extinguisher discharge, even partial, must be reported to Safety within 24 hours.
""",
    f"sop_electrical_{RUN_ID}.txt": b"""
Standard Operating Procedure: Electrical Lockout-Tagout (SOP-EL-310)

Section 1: Purpose
This procedure ensures electrical equipment is de-energized before maintenance.

Section 2: Voltage Thresholds
Any circuit above 50 volts AC or 120 volts DC requires full lockout-tagout procedure.
Verification of zero energy state must be performed with a rated voltmeter before contact.

Section 3: Lock Requirements
Each technician must apply a personal lock and tag; group lockout requires a lock box.
Locks may only be removed by the technician who applied them.

Section 4: Training
Only personnel with current Electrical Safety Certification (renewed annually) may perform LOTO.
""",
    f"sop_chemical_{RUN_ID}.txt": b"""
Standard Operating Procedure: Chemical Handling and Spill Response (SOP-CH-415)

Section 1: Personal Protective Equipment
Nitrile gloves, splash goggles, and a chemical-resistant apron are mandatory when
handling Class 2 corrosive substances.

Section 2: Storage Limits
No more than 40 liters of flammable solvent may be stored in a single cabinet.
Incompatible chemicals must be stored at least 3 meters apart.

Section 3: Spill Response
Spills exceeding 1 liter require evacuation of the immediate area and activation
of the spill response team. Spill kits are located at each chemical storage station.

Section 4: Disposal
Chemical waste must be labeled and disposed of within 90 days of generation.
""",
    f"sop_crane_{RUN_ID}.txt": b"""
Standard Operating Procedure: Crane Operations (SOP-CR-520)

Section 1: Load Limits
The maximum rated load for the Unit 4 overhead crane is 15 metric tons.
Loads must never exceed 85% of rated capacity without engineering sign-off.

Section 2: Operator Certification
Only operators holding a valid Crane Operator License (Class B or higher) may operate
overhead cranes. Certification must be renewed every 3 years.

Section 3: Pre-Operation Inspection
A visual inspection of cables, hooks, and brakes is required before every shift.

Section 4: Exclusion Zone
A 5-meter exclusion zone must be maintained around any suspended load.
""",
}

print("="*70, "\nSTEP 1: Upload synthetic SOP corpus\n" + "="*70)
uploaded = {}
for fname, content in SOPS.items():
    r = httpx.post(f"{BASE}/api/documents/upload", headers=H,
                    files={"file": (fname, io.BytesIO(content), "text/plain")}, timeout=30)
    body = r.json() if r.status_code == 200 else {"error": r.text}
    ok = r.status_code == 200 and body.get("status") in ("uploaded", "ok")
    check(f"upload {fname}", ok, str(body) if not ok else "")
    if ok:
        uploaded[fname] = body["id"]

time.sleep(1)  # let indexing settle

# NOTE: RAGSearchResult (per live /openapi.json) only has chunk_index/text/
# score now -- no filename/document_id/page. That's itself a finding (see
# summary), so precision here is checked by CONTENT match against the text,
# not by source filename, since the field isn't available to check.

print("\n" + "="*70, "\nSTEP 2: Precision -- does retrieval surface the right passage for a specific fact?\n" + "="*70)

precision_queries = [
    ("What is the maximum allowable pressure for Valve V-301?", "175", "valve"),
    ("How often must fire extinguishers be visually inspected?", "monthly", "fire"),
    ("What voltage threshold requires lockout-tagout?", "50 volts", "electrical"),
    ("How much flammable solvent can be stored in a single cabinet?", "40 liters", "chemical"),
    ("What is the maximum rated load for the Unit 4 overhead crane?", "15 metric tons", "crane"),
]

for query, expected_fact, topic in precision_queries:
    r = httpx.post(f"{BASE}/api/rag/search", headers=H, json={"query": query, "top_k": 3})
    data = r.json()
    top = data["results"][0] if data.get("results") else None
    has_fact = top and expected_fact.split()[0] in top["text"]
    check(f"precision [{topic}]: '{query[:55]}' -> top result contains '{expected_fact}'",
          has_fact, f"top={top}")

print("\n" + "="*70, "\nSTEP 3: Cross-document discrimination -- similar-sounding topics must not bleed together\n" + "="*70)

# "pressure" appears in BOTH valve (175/220 PSI) and fire extinguisher (100-175 PSI) docs.
r = httpx.post(f"{BASE}/api/rag/search", headers=H, json={"query": "maximum pressure limit for Valve V-302", "top_k": 3})
data = r.json()
top = data["results"][0] if data.get("results") else None
check("discrimination: valve-specific pressure query surfaces the 220 PSI figure (not fire safety's 100-175)",
      top and "220" in top["text"], f"got={top}")

# "certification" appears in valve, electrical, AND crane docs
r = httpx.post(f"{BASE}/api/rag/search", headers=H, json={"query": "what certification does a crane operator need", "top_k": 3})
data = r.json()
top = data["results"][0] if data.get("results") else None
check("discrimination: crane-specific certification query surfaces crane content, not valve/electrical",
      top and ("crane" in top["text"].lower() or "class b" in top["text"].lower()), f"got={top}")

print("\n" + "="*70, "\nSTEP 4: Paraphrase robustness -- different wording, same meaning\n" + "="*70)

paraphrase_queries = [
    ("How big of a gap do I need around a hanging load from the crane?", "exclusion zone", "crane"),
    ("What protective gear do I need for corrosive chemicals?", "gloves", "chemical"),
    ("Who is allowed to remove a lockout lock?", "lock", "electrical"),
]
for query, expected_fragment, topic in paraphrase_queries:
    r = httpx.post(f"{BASE}/api/rag/search", headers=H, json={"query": query, "top_k": 3})
    data = r.json()
    top = data["results"][0] if data.get("results") else None
    check(f"paraphrase [{topic}]: '{query[:50]}' -> retrieves relevant passage",
          top and expected_fragment.lower() in top["text"].lower(), f"got={top}")

print("\n" + "="*70, "\nSTEP 5: Honesty -- irrelevant query must return nothing, not a forced match\n" + "="*70)

r = httpx.post(f"{BASE}/api/rag/search", headers=H, json={"query": "what is the recommended lunch menu for the cafeteria"})
data = r.json()
check("irrelevant query returns empty results (not a forced low-relevance match)",
      data.get("status") == "ok" and len(data.get("results", [])) == 0, str(data))

print("\n" + "="*70, "\nSTEP 6: Full agent pipeline -- RAG retrieval combined with LLM synthesis\n" + "="*70)

def agent(prompt, timeout=90):
    r = httpx.post(f"{BASE}/api/agent", headers=H, json={"prompt": prompt}, timeout=timeout)
    return r.json()

d = agent("According to the SOP, what is the maximum rated load for the Unit 4 crane, and what percentage should never be exceeded without sign-off?")
tools = [s["tool"] for s in d.get("steps", [])]
final = d.get("final_output", "")
check("agent pipeline uses rag_search", "rag_search" in tools, f"tools={tools}")
check("agent final answer contains correct load figure (15)", "15" in final, final[:300])
check("agent final answer contains correct percentage (85)", "85" in final, final[:300])

d2 = agent("According to the SOP, what PPE is required for handling corrosive chemicals, and how much solvent can be stored in one cabinet?")
tools2 = [s["tool"] for s in d2.get("steps", [])]
final2 = d2.get("final_output", "")
check("agent multi-fact query -> rag_search used", "rag_search" in tools2, f"tools={tools2}")
check("agent answer mentions PPE items (glove/goggle/apron)",
      any(w in final2.lower() for w in ["glove", "goggle", "apron"]), final2[:300])
check("agent answer mentions correct storage limit (40)", "40" in final2, final2[:300])

# Cross-document comparison through the agent
d3 = agent("Compare the certification renewal periods: crane operators vs electrical LOTO technicians, according to the SOPs.")
final3 = d3.get("final_output", "")
check("cross-doc comparison mentions crane cert period (3 years)", "3 year" in final3.lower() or "3-year" in final3.lower(), final3[:400])
check("cross-doc comparison mentions electrical cert period (annually/1 year)",
      "annual" in final3.lower() or "1 year" in final3.lower() or "yearly" in final3.lower(), final3[:400])

print("\n" + "="*70, "\nSTEP 7: Citation metadata check (schema-level finding, not pass/fail on content)\n" + "="*70)

r = httpx.post(f"{BASE}/api/rag/search", headers=H, json={"query": "spill response for chemical spills", "top_k": 3})
data = r.json()
top = data["results"][0] if data.get("results") else None
has_citation_fields = top is not None and ("filename" in top or "document_id" in top or "page" in top)
check("standalone /api/rag/search results include source attribution (filename/document_id/page)",
      has_citation_fields, f"available fields: {list(top.keys()) if top else 'no results'}")

d4 = agent("What does the SOP say about spill response for chemical spills over 1 liter?")
rag_steps = [s for s in d4.get("steps", []) if s["tool"] == "rag_search"]
if rag_steps:
    td = rag_steps[0].get("tool_data") or {}
    citations = td.get("citations", [])
    check("agent-pipeline rag_search step carries citation metadata in tool_data",
          len(citations) > 0, str(td)[:300])
else:
    check("agent-pipeline rag_search step carries citation metadata in tool_data",
          False, f"no rag_search step in {[s['tool'] for s in d4.get('steps', [])]}")

print("\n" + "="*70 + "\nCLEANUP\n" + "="*70)
for fname, doc_id in uploaded.items():
    r = httpx.delete(f"{BASE}/api/documents/{doc_id}", headers=H)
    print(f"  deleted {fname}: {r.status_code}")

print("\n" + "="*70 + "\nSUMMARY\n" + "="*70)
n_pass = sum(1 for s,_,_ in results if s == "PASS")
n_fail = sum(1 for s,_,_ in results if s == "FAIL")
print(f"{n_pass} passed, {n_fail} failed out of {len(results)}")
if n_fail:
    print("\nFAILURES:")
    for s, label, detail in results:
        if s == "FAIL":
            print(f"  - {label}")
            if detail:
                print(f"    {detail[:250]}")
