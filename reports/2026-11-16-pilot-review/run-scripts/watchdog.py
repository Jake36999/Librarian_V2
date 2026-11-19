"""Exit (one notification) when the ingestion needs attention: a stall, a stop, an error, or the end."""
import glob, json, os, sys, time
S = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(S, "phases.out")
USAGE = r"G:\Libraries\Nonlinear Field Lab\.librarian\runtime"
STALL = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
pos = os.path.getsize(OUT)
while True:
    with open(OUT, encoding="utf-8", errors="replace") as h:
        h.seek(pos); chunk = h.read(); pos = h.tell()
    for line in chunk.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            if line.strip():
                print("NON-JSON line from the runner:", line[:400]); sys.exit(0)
            continue
        if r.get("step") in ("ceiling", "finished", "folder_error", "stopped") or r.get("error") \
                or (r.get("phase") == "B-research" and r.get("step") == "begin"):
            print(json.dumps(r)[:1200]); sys.exit(0)
    newest = max((os.path.getmtime(f) for f in glob.glob(os.path.join(USAGE, "usage-*.jsonl"))), default=time.time())
    if time.time() - newest > STALL:
        print(f"STALL: no model call logged for {int(time.time() - newest)} s"); sys.exit(0)
    time.sleep(30)
