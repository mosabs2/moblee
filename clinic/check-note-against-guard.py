"""Feed every fenced shell command in the clinic note through bash-guard.py and report any that it would block."""
import json, re, subprocess, sys

note = sys.argv[1]
guard = sys.argv[2]
text = open(note).read()
blocks = re.findall(r"```\n(.*?)```", text, re.S)
blocked, passed = [], 0
for b in blocks:
    s = b.strip()
    if s.startswith(("import ", "---", "- **")):  # python file, frontmatter, prose
        continue
    # multi-line python3 -c blocks are one command; everything else one command per line
    cmds = [s] if "python3 -c" in s else [l for l in s.splitlines() if l.strip()]
    for c in cmds:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": c}})
        r = subprocess.run([sys.executable, guard], input=payload, capture_output=True, text=True)
        if r.returncode != 0:
            blocked.append((r.returncode, c[:110], (r.stderr or r.stdout).strip()[:160]))
        else:
            passed += 1
print(f"commands passed: {passed}; blocked: {len(blocked)}")
for rc, c, msg in blocked:
    print(f"\nEXIT {rc}: {c}\n   -> {msg}")
