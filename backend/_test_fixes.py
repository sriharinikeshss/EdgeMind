import httpx, sys, io, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "http://localhost:8000"

token = httpx.post(f"{BASE}/api/auth/login", data={"username": "admin", "password": "kavach123"}).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

def agent(prompt, timeout=120):
    t0 = time.monotonic()
    r = httpx.post(f"{BASE}/api/agent", headers=H, json={"prompt": prompt}, timeout=timeout)
    dt = time.monotonic() - t0
    return r.json(), dt

print("="*70, "\nTEST 1: trivial greeting -- expect single direct_llm step, no artifact, fast\n" + "="*70)
for p in ["hi", "hello", "thanks", "how are you"]:
    d, dt = agent(p)
    tools = [s["tool"] for s in d.get("steps", [])]
    ok = tools == ["direct_llm"]
    print(f"[{ 'PASS' if ok else 'FAIL' }] '{p}' -> steps={tools} ({dt:.1f}s)")
    print("    output:", (d.get("final_output") or "")[:200].replace("\n", " "))

print("\n" + "="*70, "\nTEST 2: casual short task -- no artifact, still answers properly\n" + "="*70)
d, dt = agent("Write a haiku about the ocean")
tools = [s["tool"] for s in d.get("steps", [])]
ok = "generate_docx" not in tools and "generate_pdf" not in tools
print(f"[{ 'PASS' if ok else 'FAIL' }] haiku request -> steps={tools} ({dt:.1f}s)")
print("    output:", (d.get("final_output") or "")[:300].replace("\n", " "))

print("\n" + "="*70, "\nTEST 3: explicit artifact request -- SHOULD still generate a docx\n" + "="*70)
d, dt = agent("Draft an approval note summarizing that Valve V-200's inspection passed, and generate it as a downloadable Word document.")
tools = [s["tool"] for s in d.get("steps", [])]
ok = "generate_docx" in tools
print(f"[{ 'PASS' if ok else 'FAIL' }] explicit docx request -> steps={tools} ({dt:.1f}s)")
for s in d.get("steps", []):
    if s["tool"] == "generate_docx":
        print("    generate_docx output:", (s.get("output") or s.get("error") or "")[:300])

print("\n" + "="*70, "\nTEST 4: a real multi-step task not touched by the fix -- should still work\n" + "="*70)
d, dt = agent("Calculate the square root of 144 using Python and explain the result.")
tools = [s["tool"] for s in d.get("steps", [])]
ok = "execute_python" in tools and d.get("status") == "COMPLETED"
print(f"[{ 'PASS' if ok else 'FAIL' }] calc task -> steps={tools} status={d.get('status')} ({dt:.1f}s)")
print("    output:", (d.get("final_output") or "")[:300].replace("\n", " "))
