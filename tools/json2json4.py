import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f_in, open(sys.argv[2], "w", encoding="utf-8") as f_out:
    f_out.write(json.dumps(json.loads(f_in.read()), indent=4))