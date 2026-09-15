import time
from collections.abc import Generator
from copy import deepcopy
from typing import Literal

try:
    # pyrefly: ignore [missing-import]
    import orjson
except ImportError as e:
    print(e)
    import json
    class orjson:
        @staticmethod
        def loads(x):
            return json.loads(x)
        @staticmethod
        def dumps(x):
            return json.dumps(x).encode()
import requests

from enboite.lib import tooling


class client:
    def __init__(
        self,
        model: Literal[
            "gemma4:26b",
            "qwen3.8:27b",
            "qwen3:14b",
            "qwen3.6:35b-a3b",
            "ornith-1.5:35b",
            "qwen3:8b"
        ] | str,
        think: bool|None = None,
        system_prompt: str|None = None,
        num_ctx: int|None = None,
        keep_alive: str|int|None = None,
        tools: list|None = None,
        endpoint: str = "http://127.0.0.1:11434",
        proxy: str|None = None,
        timeout: None|int = None,
        printError: bool = True
    ) -> None:
        self.model = model
        self.think = think
        self.system_prompt = system_prompt
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.endpoint = endpoint
        self.tools = tools
        self.timeout = timeout
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": "EnBoite/0.0.0"
        })
        self.messages: list[dict] = []
        self.total_token = 0
        self.token_per_sec = 0
        self._systemPrompt()
        self.printError = printError
        if proxy:
            self.http.proxies.update(
                {
                    "http": f"socks5h://{proxy}",
                    "https": f"socks5h://{proxy}"
                }
            )
    
    def clear(self):
        self.messages = []
        self._systemPrompt()
    
    def export(self) -> bytes:
        messages = deepcopy(self.messages)
        
        if messages[0]["role"] == "system":
            del messages[0]
        else:
            raise RuntimeError("not found the system prompt:67")
        
        return orjson.dumps(messages)
    
    def load(self, x: bytes) -> None:
        self.messages = orjson.loads(x)
        self._systemPrompt()
    
    def _systemPrompt(self):
        if self.system_prompt:
            data = [
                {
                    "role": "system",
                    "content": self.system_prompt
                }
            ]
            data.extend(self.messages)
            self.messages = data
    
    def debug_chat(self):
        for i in self.messages:
            for key, value in i.items():
                print(f"{key} > {str(value)[:100]}")
    
    def get(self, message: str|None = None):
        response = self.http.post(
            f"{self.endpoint}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user","content": message,}] if message else self.messages,
                "stream": True,
                **({"think": self.think} if self.think is not None else {}),
                **({"tools": self.tools} if self.tools is not None else {}),
                **({"keep_alive": self.keep_alive} if self.keep_alive is not None else {}),
                "options": {
                    **({"num_ctx": self.num_ctx} if self.num_ctx is not None else {}),
                }
            },
            timeout=self.timeout,
            stream=True
        )
        return response
    
    def generate_raw(self, content: str) -> Generator[dict]:
        if content != "":
            self.messages.append(
                {
                    "role": "user",
                    "content": content,
                }
            )
        
        del content
        
        response = self.get()
        
        if response.status_code != 200:
            print(self.debug_chat())
            print(response.text)
            response.raise_for_status()
        
        content = ""
        # thinking = ""
        tool_calls = []
        
        for line in response.iter_lines(chunk_size=1):
            line: bytes
            if not line:
                continue
            
            data = orjson.loads(line)
            message = data.get("message", {})
            
            if chunk := message.get("content"):
                content += chunk
                yield {"type": "content", "content": chunk}
            
            if chunk := message.get("thinking"):
                yield {"type": "thinking", "content": chunk}
            
            if calls := message.get("tool_calls"):
                for i in calls:
                    yield {"type": "tool", "function": i.get("function")}
                tool_calls.extend(calls)
            
            if data.get("done"):
                self.total_token = max(self.total_token, data.get("prompt_eval_count", 0) + data.get("eval_count", 0))
                self.token_per_sec = data["eval_count"] / (data["eval_duration"] / 1e9)
                if content: yield {"type": "content", "content": "\n"}
                yield {"type": "done"}
                break
        
        self.messages.append({
            "role": "assistant",
            "content": content,
            **({"tool_calls": tool_calls} if tool_calls else {})
        })
        
        yield {"type": "tool_calls", "content": tool_calls}
        return None
    
    def generate(self, content: str) -> Generator[dict]:
        while True:
            tool_calls =  []
            stream = self.generate_raw(content)
            content = ""
            for chunk in stream:
                if chunk["type"] in ["thinking", "content", "tool", "done"]:
                    yield chunk
                elif chunk["type"] == "tool_calls":
                    tool_calls.extend(chunk["content"])
                else:
                    raise RuntimeError("invalid key in [type]")
            
            if len(tool_calls) == 0:
                break
            
            for call in tool_calls:
                function = call["function"]
                
                name = function["name"]
                arguments = function["arguments"]
                
                try:
                    # pyrefly: ignore [unsupported-operation]
                    func = getattr(tooling, name)
                    if func.__module__ != tooling.__name__:
                        raise ValueError("Tool externe")
                    
                    tool_result = func(**arguments)
                except Exception as e:  # noqa: BLE001
                    tool_result = f"Tool '{name}' failed: {type(e).__name__}: {e}"
                    if self.printError:
                        print(f"\033[41m{tool_result}\033[0m")
                
                images = None
                if type(tool_result) is dict and tool_result['type'] == "images":
                    images = tool_result["value"]
                    tool_result = tool_result.get('content', "")
                
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": str(tool_result),
                        **({"images": images} if images else {}),
                    }
                )
    
    def unload_llm(self) -> None:
        i = 0
        think_old = self.think
        keep_old = self.keep_alive
        self.think = False
        self.keep_alive = 0
        while self.http.get(f"{self.endpoint}/api/ps").json()["models"]:
            i+= 0.5
            print("unload...")
            print(f"...({i}s)")
            self.get("Do not respond at all.")
            time.sleep(i)
        print("ok")
        self.think = think_old
        self.keep_alive = keep_old