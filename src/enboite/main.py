import argparse
import datetime
import importlib
import importlib.resources
import io
import json
import os
import sys
import time
from collections.abc import Callable
from io import BytesIO

import prompt_toolkit
import prompt_toolkit.history

sd = sf = None
try:
    # pyrefly: ignore [missing-import]
    import sounddevice as sd
    
    # pyrefly: ignore [missing-import]
    import soundfile as sf
except ImportError as e:
    print(e)

import inspect
import shutil
from pathlib import Path

import tomlkit
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text
from tqdm import tqdm

from enboite.lib import TTS, llm, tooling
from enboite.lib import color as c
from enboite.lib import tooling as t


def clear_tmp(folder: str):
    for item in Path(folder).iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def speaker(content: bytes) -> None:
    if sd and sf:
        audio, sample_rate = sf.read(BytesIO(content))
        sd.play(audio, sample_rate)
        sd.wait()

def _prompt(x: list[str]) -> str:
    return "".join([line for line in x if not line.lstrip().startswith(">")])


def loadToolings() -> dict[str, Callable[..., bool|str|dict[str, str]]]:
    functions = {}
    
    for name in dir(tooling):
        func = getattr(tooling, name)
        
        if not name.startswith("_"):  # noqa: SIM102
            if inspect.isfunction(func) and func.__module__ == tooling.__name__:
                functions[name] = func
    return functions

def loadConfig(x: str):
    conf = os.path.join(x, "config.toml")
    if os.path.isfile(conf):
        with open(conf, "r", encoding="utf-8") as f:
            data = tomlkit.loads(f.read())
    else:
        table = tomlkit.table()
        # for key in loadToolings():
        #     if not key.startswith(("TTS", "keyboard")):
        #         table.add(key, True)
        #     else:
        #         table.add(key, False)
        data = tomlkit.document()
        data["tools"] = table
        with open(conf, "w", encoding="utf-8") as f:
            f.write(data.as_string())
    return data



def _main(
    model: str|None,
    prompt: str|None,
    save_chat: bool,
    thinking: bool,
    limit_content_size: int | None,
    dbg_tools: bool,
    llm_ctx: int|None,
    endpoint: str,
    proxy: str|None,
    android: bool,
    prompt_file: None|str,
    non_interactive: bool,
    data_dir: None|str,
    enable_tools: list[str],
    disable_tools: list[str],
    no_tools: bool
    #config: None|str
):
    if prompt_file:
        prompt = open(prompt_file, "r", encoding="utf-8").read()  # noqa: SIM115
    
    t.DOCKER_CONTAINER_MAX = 1
    t.INTERACTIVE = not non_interactive
    
    if data_dir:
        t._set_base(data_dir)
    elif android:
        t._set_base(str((Path("/storage/emulated/0") / "Documents" / "enboite-share").resolve()))
    else:
        t._set_base(str((Path.home() / "Documents" / "enboite-share" ).resolve()))
    
    clear_tmp(os.path.join(t.BASE_SHARE, "tmp"))
    
    config = loadConfig(str(t.BASE_BASE))
    tools = []
    
    total_tools = loadToolings()
    print("="* 40)
    print("==== tools ====")
    for func_name, func in total_tools.items():
        if func_name in disable_tools:
            use = False
        elif func_name in enable_tools:
            use = True
        elif no_tools:
            use = False
        else:
            use = config["tools"].get(func_name, False)
            if not use and not func_name.startswith(("TTS", "keyboard")):
                use = True
        
        if use:
            print(f"{c.GREEN}use       : {func_name}{c.RESET}")
            tools.append(func)
        else:
            print(f"{c.YELLOW}not use   : {func_name} {c.RESET}")
    print("="* 40)
    
    # save_chat_file = os.path.join(str(t.BASE_BASE), "chat.log.bin")
    
    tools = tooling._build_v2(tools)
    if dbg_tools:
        print(json.dumps(tools, indent=4))
    
    session = llm.client(
        model or "qwen3:14b" or "qwen3.8:27b",  # noqa: SIM222
        think=thinking,
        num_ctx=llm_ctx,
        tools=tools,
        system_prompt=_prompt(open(str(importlib.resources.files("enboite").joinpath("prompt.md")), "r", encoding="utf-8").readlines()),  # noqa: SIM115
        keep_alive="20m",
        endpoint=endpoint,
        proxy=proxy
    )
    t.SESSION_LLM = session
    
    for f in Path(os.path.join(t.BASE_BASE, "tools")).glob("*.py"):
        t._tool_load(f.stem)
    
    if save_chat:
        if not non_interactive:
            chats: list[tuple[str, str]] = []
            for file in Path(t.BASE_BASE).glob("chat.log*.bin"):
                title = None
                chat_meta = Path(os.path.join(str(t.BASE_BASE), f"{Path(file).stem}.json"))
                if os.path.isfile(chat_meta):
                    with open(chat_meta, "r") as f:
                        title = json.loads(f.read()).get("title", None)
                
                with open(str(file), "r", encoding="utf-8") as f_f:
                    JSON = json.loads(f_f.read())
                    chats.append(
                        (
                            str(file.resolve()),
                            title if title else (
                                Path(f_f.name).stem+" : "+(JSON[0].get("content", "")[:30] if len(JSON) > 0 else "")
                            ) + "..."
                        )
                    )
            
            chats.append(("<new>", "< Make a new chat >"))
            
            result = prompt_toolkit.shortcuts.choice(
                message="Select a chat history.",
                options=chats,
            )
            if result == "<new>":
                save_chat_file_base = os.path.join(
                    t.BASE_BASE,
                    f"chat.log-{datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d_%H-%M-%S")}"
                )
                save_chat_file = f"{save_chat_file_base}.bin"
                
                Path(save_chat_file).write_text(json.dumps([]))
                Path(f"{save_chat_file_base}.json").write_text(json.dumps({}))
            else:
                save_chat_file = result
        else:
            save_chat_file = os.path.join(str(t.BASE_BASE), "chat.log.bin")
    
    
    # pyrefly: ignore[unbound-name]
    if save_chat and os.path.isfile(save_chat_file):
        t.CHAT_META = Path(os.path.join(str(t.BASE_BASE), f"{Path(save_chat_file).stem}.json"))
        with open(save_chat_file, "rb") as f:
            session.load(f.read())
    
    rich_console = Console()
    
    
    _max_size_thinking = 500
    _max_size_tools = 500
    
    TTS_time = 1.5
    
    live = None
    input_stdin = prompt_toolkit.PromptSession(
        history=prompt_toolkit.history.FileHistory(os.path.join(t.BASE_BASE, "history.txt"))
    ).prompt
    try:
        while True:
            _input = input_stdin(">").strip() if not prompt else prompt
            TTS_last = time.monotonic()
            TTS_chunk = ""
            live = Live(
                "",
                console=rich_console,
                refresh_per_second=5
            )
            live.start()
            t.LIVE = live
            content = ""
            thinking_data = ""
            tools_data = ""
            
            if not _input.startswith("/"):
                try:
                    for chunk in session.generate(_input):
                        if chunk["type"] == "content":
                            if TTS.status():
                                TTS_chunk += chunk["content"]
                            
                            content += chunk["content"]
                            thinking_data = ""
                            if limit_content_size:
                                content = content[-limit_content_size:]
                        
                        elif chunk["type"] == "thinking":
                            thinking_data += chunk["content"]
                            thinking_data = thinking_data[-_max_size_thinking:]
                        
                        elif chunk["type"] == "tool":
                            tools_data += f'{chunk["function"]}\n'
                            tools_data = tools_data[-_max_size_tools:]
                        
                        elif chunk["type"] in ("done", "refresh"):
                            pass
                        
                        else:
                            raise RuntimeError(f"invalid type : {chunk["type"]}")
                        
                        if TTS.status() and (chunk["type"] == "done" or (time.monotonic()-TTS_time> TTS_last and len(chunk["type"]) >= 20) ):  # noqa: SIM102
                            if TTS_chunk:
                                speaker(TTS.TTSgen(TTS_chunk))
                                TTS_chunk = ""
                                TTS_last = time.monotonic()
                        
                        bar_io = io.StringIO()
                        bar = tqdm(
                            total=llm_ctx,
                            file=bar_io,
                            leave=False,
                            ascii=False
                        )
                        bar.n = session.total_token
                        bar.refresh()
                        
                        live.update(
                            Group(
                                Text(thinking_data, style="dim italic"),
                                Text(tools_data, style="bold cyan"),
                                Markdown(content),
                                "\n" + bar_io.getvalue().split("\r")[-1].strip(),
                                f"character spike : {session.spike_char}",
                                f"token/s : {session.token_per_sec}"
                            )
                        )
                    
                    if save_chat:
                        with open(save_chat_file, "wb") as f:
                            f.write(session.export())
                except KeyboardInterrupt:
                    pass
            elif _input == "/log":
                rich_console.print(json.dumps(session.messages, indent=4))
            elif _input == "/think":
                session.think = not session.think
            elif _input == "/clear":
                session.clear()
                session.total_token = 0
                with open(save_chat_file, "wb") as f:
                    f.write(session.export())
            live.stop()
            if prompt:
                sys.exit(0)
    except KeyboardInterrupt:
        pass
    finally:
        if live:
            live.stop()
        
        for container in t.DOCKER_CONTAINER_LIST:
            container.stop(timeout=1)


def main():
    parser = argparse.ArgumentParser(
        prog="EnBoite",
        description="Give your AI agent full control over a system through SSH.",
        allow_abbrev=False
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Name of the local LLM model to use."
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Text prompt to send once, then exit (non-interactive mode)."
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="Path to a file containing the prompt text."
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        type=str,
        help="Directory used to store chat history, config and tool state."
    )
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="Enable the model's reasoning."
    )
    parser.add_argument(
        "--no-save-chat",
        action="store_true",
        help="Do not save the conversation history to disk."
    )
    parser.add_argument(
        "--limit-content-size",
        type=int,
        default=None,
        help="Maximum number of characters kept for the streamed response display."
    )
    parser.add_argument(
        "--ctx",
        type=int,
        default=2048,
        help="Size of the model's context window."
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true"
    )
    parser.add_argument(
        "--enable-tools",
        nargs="+",
        type=str,
        default=[],
        help="List of tools to force-enable."
    )
    parser.add_argument(
        "--disable-tools",
        nargs="+",
        type=str,
        default=[],
        help="List of tools to force-disable"
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Deactivates all tools."
    )
    parser.add_argument(
        "--dbg-tools",
        action="store_true",
        help="Print the full tool schema (JSON) for debugging."
    )
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:11434",
        help="Base URL of the LLM API endpoint (default: http://127.0.0.1:11434)."
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL used to reach the LLM endpoint (e.g. socks5h://127.0.0.1:9050)."
    )
    parser.add_argument(
        "--android",
        help="Must be enabled if the system is Termux/Android; only Android has been verified.",
        action="store_true"
    )
    args = parser.parse_args()
    
    _main(
        prompt=args.prompt,
        save_chat=not args.no_save_chat,
        dbg_tools=args.dbg_tools,
        thinking=args.thinking,
        limit_content_size=args.limit_content_size,
        llm_ctx=args.ctx,
        model=args.model,
        endpoint=args.endpoint,
        proxy=args.proxy,
        android=args.android,
        prompt_file=args.prompt_file,
        non_interactive=args.non_interactive,
        data_dir=args.data_dir,
        #config=args.config
        enable_tools=args.enable_tools,
        disable_tools=args.disable_tools,
        no_tools=args.no_tools
    )