import argparse
import io
import json
import os
import sys

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text
from tqdm import tqdm

from enboite.lib import llm, tooling
from enboite.lib import tooling as t


def _main(
    model: str|None,
    prompt: str|None,
    save_chat: bool,
    thinking: bool,
    limit_content_size: int | None,
    dbg_tools: bool,
    llm_ctx: int|None
):
    save_chat_file = "chat.log.bin"
    
    t.DOCKER_CONTAINER_MAX = 1
    
    tools: list = [
        t.get_time,
        t.ls,
        t.cat,
        # t.execute,
        t.ssh_login,
        t.ssh_commande,
        t.ssh_close,
        t.notify,
        t.system,
        t.get_ip,
        t.get_geo_ip,
        t.search_web,
        t.fetch_url_v1,
        t.ssh_tranfer_client2hote,
        t.container_start,
        t.container_images,
        t.screenshot,
        t.read_media,
        
        t.test
    ]
    tools = tooling.build_v2(tools)
    if dbg_tools:
        print(json.dumps(tools, indent=4))
    
    session = llm.client(
        model or "qwen3.8:27b",
        think=thinking,
        num_ctx=llm_ctx,
        tools=tools,
        system_prompt=open("./prompt.txt", "r", encoding="utf-8").read(),  # noqa: SIM115
        keep_alive="20m"
    )
    
    if save_chat and os.path.isfile(save_chat_file):
        with open(save_chat_file, "rb") as f:
            session.load(f.read())
    
    rich_console = Console()
    
    
    _max_size_thinking = 500
    _max_size_tools = 500
    
    live = None
    try:
        while True:
            _input = rich_console.input(">") if not prompt else prompt
            live = Live(
                "",
                console=rich_console,
                refresh_per_second=10
            )
            live.start()
            content = ""
            thinking_data = ""
            tools_data = ""
            
            if not _input.startswith("/"):
                try:
                    for chunk in session.generate(_input):
                        if chunk["type"] == "content":
                            content += chunk["content"]
                            if limit_content_size:
                                content = content[-limit_content_size:]
                        
                        elif chunk["type"] == "thinking":
                            thinking_data += chunk["content"]
                            thinking_data = thinking_data[-_max_size_thinking:]
                        elif chunk["type"] == "tool":
                            tools_data += f'function : {chunk["function"]}\n'
                            tools_data = tools_data[-_max_size_tools:]
                        
                        elif chunk["type"] == "done":
                            pass
                        
                        else:
                            raise RuntimeError(f"invalid type : {chunk["type"]}")
                        
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
                            )
                        )
                except KeyboardInterrupt:
                    pass
            elif _input == "/log":
                rich_console.print(json.dumps(session.messages, indent=4))
            elif _input == "/think":
                session.think = not session.think
            elif _input == "/clear":
                session.clear()
                session.total_token = 0
            live.stop()
            if prompt:
                sys.exit(0)
    except KeyboardInterrupt:
        pass
    finally:
        if save_chat:
            with open(save_chat_file, "wb") as f:
                f.write(session.export())
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
        default=None
    )
    parser.add_argument(
        "--prompt",
        default=None
    )
    parser.add_argument(
        "--thinking",
        action="store_true"
    )
    parser.add_argument(
        "--no-save-chat",
        action="store_true"
    )
    parser.add_argument(
        "--limit-content-size",
        type=int,
        default=None
    )
    parser.add_argument(
        "--llm-ctx",
        type=int,
        default=1024
    )
    parser.add_argument(
        "--dbg-tools",
        action="store_true"
    )
    args = parser.parse_args()
    
    _main(
        prompt=args.prompt,
        save_chat=not args.no_save_chat,
        dbg_tools=args.dbg_tools,
        thinking=args.thinking,
        limit_content_size=args.limit_content_size,
        llm_ctx=args.llm_ctx,
        model=args.model
    )