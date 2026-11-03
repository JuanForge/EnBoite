import json
import os
import sys

# import orjson
# 
# OPTIMIZE: bool = False

if not os.path.isfile(sys.argv[1]):
    raise FileNotFoundError()
if not os.path.isdir(sys.argv[2]):
    raise FileNotFoundError("folder")

with open(sys.argv[1], "r", encoding="utf-8") as f:
    RESULT: dict[
        str,
        list[
            dict[str, str]
        ]
    ] = {}
    
    JSON = json.loads(f.read())
    for conv in JSON["conversations"]:
        ID = conv["conversation"]["id"]
        chat: list[dict[str, str]] = []
        for _element in conv["responses"]:
            sender = None
            if _element["response"]["sender"] == "human":
                sender = "user"
            elif _element["response"]["sender"] == "assistant":
                sender = "assistant"
            
            if sender:
                chat.append({"role": sender, "content": _element["response"]["message"]})
        RESULT[ID] = chat
    
    for ID, chat in RESULT.items():
        with open(os.path.join(sys.argv[2], f"{ID}.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(chat, indent=4))