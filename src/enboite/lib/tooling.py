from __future__ import annotations

import datetime as dt
import inspect
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from pprint import pprint  # noqa: F401
from typing import TYPE_CHECKING, Any, get_args

import cpuinfo
import distro
import humanize

# pyrefly: ignore [untyped-import]
import psutil
from pydantic import TypeAdapter
from rich.live import Live as rich_Live
from screeninfo import get_monitors

FS_PERMIT_HOST: bool = False


class _client:
    class UserRefusedError(Exception):
        def __init__(self):
            super().__init__(
                "The user explicitly refused to allow this tool execution.\n"
                "Do not retry the tool call. The user, not the tool, refused the execution. Do not call this tool again during the current turn. You may use it again only after receiving a new user message."
            )
    class FS:
        class HostAccessDeniedError(Exception):
            def __init__(self):
                super().__init__(
                    "Host filesystem access is disabled by user"
                )

TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    type(None): "null",
}


def get_json_type(python_type):
    if python_type in TYPE_MAP:
        return TYPE_MAP[python_type]
    
    args = get_args(python_type)
    
    if args:
        return [TYPE_MAP[arg] for arg in args]
    
    raise TypeError(f"Type non supporté : {python_type}")

def build(funcs):
    if not type(funcs) is list:
        funcs = [funcs]
    
    result: list = []
    for func in funcs:
        signature = inspect.signature(func)
        
        properties = {}
        required = []
        
        for name, param in signature.parameters.items():
            python_type = param.annotation
            
            properties[name] = {
                "type": get_json_type(python_type)
            }
            
            if param.default is inspect.Parameter.empty:
                required.append(name)
        
        result.append({
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": func.__doc__ or "",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return result


def build_v2(funcs):
    funcs = funcs if isinstance(funcs, list) else [funcs]
    return [
        {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": inspect.getdoc(func) or "",
                "parameters": {
                    "type": "object",
                    "properties": {
                        name: TypeAdapter(param.annotation).json_schema(union_format="primitive_type_array")
                        for name, param in inspect.signature(func).parameters.items()
                    },
                    "required": [
                        name
                        for name, param in inspect.signature(func).parameters.items()
                        if param.default is inspect.Parameter.empty
                    ],
                },
            },
        }
        for func in funcs
    ]


class add:
    def __init__(self):
        self.result = ""
    def __call__(self, *args) -> None:
        for i in args:
            self.result += f"\n{i}"

LIVE: None | rich_Live = None

def _input_live(*args, y_n: bool=True, color: bool=False) -> str|bool:
    try:
        if LIVE:
            LIVE.stop()
    except Exception as e:  # noqa: BLE001
        print(e)
    for i in args:
        if color: i = f"\033[48;5;22m\033[38;5;15m{i}\033[0m"
        print(str(i).replace("\n", "\n ") +"\n")
    
    value = input("input requit y/n >" if y_n else "input requit >").strip()
    
    try:
        if LIVE:
            LIVE.start()
    except Exception as e:  # noqa: BLE001
        print(e)
    
    if y_n:
        return value in ["y", "yes"]
    
    
    return value

# pyrefly: ignore [bad-assignment]
BASE_BASE: Path = None
# pyrefly: ignore [bad-assignment]
BASE_SHARE: Path = None
# pyrefly: ignore [bad-assignment]
BASE_NOTE: Path = None

def set_base(path: str) -> None:
    global BASE_BASE, BASE_SHARE, BASE_NOTE
    BASE_BASE = Path(path)
    BASE_SHARE = Path(path).joinpath("share")
    BASE_NOTE = Path(path).joinpath("note-v2")
    os.makedirs(BASE_BASE, exist_ok=True)
    os.makedirs(BASE_SHARE, exist_ok=True)
    os.makedirs(BASE_NOTE, exist_ok=True)

def _secure_path(input: str, make: bool = True):
    """RAISE"""
    _input = Path(input)
    if _input.is_absolute():
        raise ValueError("Absolute path prohibited")
    
    path = (BASE_SHARE / _input).resolve()
    if not path.is_relative_to(BASE_SHARE):
        raise ValueError("Path traversal forbidden")
    
    if make:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    
    return Path(path)



def get_time():
    """
    Provides the user's local time and other time-related information.
    """
    return datetime.now().astimezone()


def execute(commande: str):
    """
    permet d'exécuter une commande dans un terminal Bash.
    Avant l'action, demander l'autorisation de l'utilisateur pour exécuter la commande.
    Et une autorisation supplémentaire sera également demandée à l'utilisateur.
    """
    print("\n")
    print("\033[41m" + repr(commande) + "\033[0m")
    print("\n" + "\033[41m" + "Allow the execution of this command generated by the agent?" + "\033[0m")
    
    if input("yes\\no >") == "yes":
        rs = subprocess.run(
            commande,
            shell=True,
            capture_output=True,
            text=True,
            check=False
            )
        return f"stdout : {rs.stdout}, stderr : {rs.stderr}, returncode : {rs.returncode}"
    else:
        return "The user refused the execution request."





# pyrefly: ignore [unknown-name]
ssh_objet: paramiko.SSHClient | None = None  # noqa: F821

def ssh_login(ip: str, port: int, username: str, password: str, key_filename: str|None = None):
    """
    Creates a persistent SSH connection.
    """
    # pyrefly: ignore [missing-import]
    import paramiko
    
    global ssh_objet
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ssh.connect(
        hostname=ip,
        port=port,
        username=username,
        password=password,
        key_filename=key_filename,
        timeout=10
    )
    ssh_objet = ssh

def ssh_commande(commande: str, timeout: int = 20):
    """
    Executes the specified command on the SSH session previously created by ssh_login.
    - timeout:
               Maximum timeout: 300 seconds
               Default timeout: 20 seconds
    """
    if ssh_objet is None:
        return "No SSH connection was created beforehand; use 'ssh_login'."
    
    stdin, stdout, stderr = ssh_objet.exec_command(commande, timeout=min(300, timeout))  # noqa: RUF059
    
    return f"stdout : {stdout.read().decode()}, error : {stderr.read().decode()}, returncode : {stdout.channel.recv_exit_status()}"

def ssh_tranfer_client2hote(file_source: str, file_hote: str):
    """
    Allows transferring a file (files only) from the SSH connection to the user's machine.
    The tool only accepts relative file paths.
    """
    if ssh_objet is None:
        return "No SSH connection was created beforehand."
    
    file = _secure_path(file_hote)
    
    ssh_objet.open_sftp().get(
        file_source,
        file
    )
    return f"True, file hote is : {file}"

def ssh_tranfer_hote2client(file_hote: str, file_client: str) -> str:
    """
    copier un fichier local sur le serveur ssh
    """
    if ssh_objet is None:
        return "No SSH connection was created beforehand."
    
    file = _secure_path(file_hote)
    
    ssh_objet.open_sftp().put(
        file,
        file_client
    )
    return f"True, file client is : {file_client}"

def ssh_close():
    """
    Close the previously established connection.
    """
    global ssh_objet
    if ssh_objet is None:
        return "No SSH connection was created beforehand."
    
    ssh_objet.close()
    ssh_objet = None
    return True


def notify(title: str, message: str):
    """
    Sends a desktop notification to the user's operating system.
    The notification is displayed by the user's desktop environment.
    """
    # pyrefly: ignore [missing-import]
    from notifypy import Notify

    notification = Notify()
    notification.title = title
    notification.message = message
    notification.send()
    return True

def system():
    """
    Provides a comprehensive report of system information,
    including the operating system, hardware, and other available details.
    
    Available information: display, OS, CPU, RAM, storage, etc.
    """
    _ = add()
    _("=== OS ===")
    _("Système :", platform.system())
    _("Distribution :", distro.name())
    _("Version :", distro.version())
    _("Kernel :", platform.release())
    _("Architecture :", platform.machine())
    _("\n=== CPU ===")
    _("CPU :", cpuinfo.get_cpu_info().get("brand_raw"))
    _("Ceurs physiques :", psutil.cpu_count(logical=False))
    _("Threads :", psutil.cpu_count(logical=True))
    _("\n=== RAM ===")
    ram = psutil.virtual_memory()
    _("Total :", round(ram.total / 1024**3, 2), "GB")
    _("Utilisée :", round(ram.used / 1024**3, 2), "GB")
    _("\n=== DISQUES ===")
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            _(
                partition.device,
                partition.mountpoint,
                f"{usage.total / 1024**3:.1f} GB"
            )
        except PermissionError:
            pass
    
    _("\n=== ÉCRANS ===")
    for monitor in get_monitors():
        _(
            monitor.name,
            f"{monitor.width}x{monitor.height}",
            f"@ ({monitor.x}, {monitor.y})"
        )
    return _.result


import socket

import requests


def get_ip():
    """
    permet d'avoir l'ip local utilisé pour les connexion, et l'ip publique
    """
    def get_ip(url: str) -> str | None:
        try:
            r = requests.get(url, timeout=3)
            r.raise_for_status()
            return r.text.strip()
        except requests.RequestException as e:
            return f"error : '''{e}'''"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return f"local : {ip}, public_IPv4 : {get_ip("https://api.ipify.org")}, public_IPv6 : {get_ip("https://api6.ipify.org")}"


def get_geo_ip(ip: str):
    """
    Provides geolocation information for an IP address using GeoLite2-City,
    including the geographic coordinates (latitude and longitude).
    """
    # pyrefly: ignore [missing-import]
    import geoip2.database
    
    with geoip2.database.Reader("GeoLite2-City.mmdb") as reader:
        _ = add()
        response = reader.city(ip)
        #pprint(response, depth=None)
        _("continent: ", response.continent.name)
        _("country: ", response.country.name)
        _("subdivisions: ", ", ".join([i.name for i in response.subdivisions]))
        _("city: ", response.city.name)
        _("city_postal: ", response.postal.code)
        _("latitude: ", response.location.latitude)
        _("longitude: ", response.location.longitude)
        return _.result

from ddgs import DDGS


def search_web(query: str, max_results: int = 5):
    """
    permet une recherche web,
    retourne un enssemble de réponses.
    recu : URL, titre, courte description
    
    - max_results:
        spécifier le nombre de résultat. defaut 5, max 15, min 1.
    """
    max_result = 15
    
    _ = add()
    return "\n\n".join(
        f"Titre : {r['title']}\n"
        f"URL : {r['href']}\n"
        f"Description : {r['body']}"
        for r in DDGS().text(query, max_results=max(1, min(max_result, max_results)))
    )


def fetch_url_v1(url: str):
    """
    retourne le contenue d'une page.
    format : markdown
    """
    return DDGS().extract(
        url,
        fmt="text_markdown",
    )["content"]

def fetch_url_raw_v1(url: str, proxy: str|None = None):
    """
    retourne le contenue d'une page.
    format : html/raw
    
    - proxy:
            - exmanples:
                        "socks5h://127.0.0.1:9050"
    """
    
    kwargs = {}
    
    if proxy:
        kwargs["proxies"] = {
            "http": proxy,
            "https": proxy,
        }
    
    # pyrefly: ignore [bad-argument-type]
    return requests.get(url, **kwargs).text

import secrets

DOCKER_CONTAINER_MAX:int = 1
# pyrefly: ignore [unknown-name]
DOCKER_CONTAINER_LIST:list[docker.models.containers.Container] = []  # noqa: F821
DOCKER_CONTAINER_PULL: bool = False


def container_start(
    image: str|None = None,
    gpus: list[int]|int|None = None
) -> str:
    """
    Creates a container on the user's machine.
    The container includes an SSH server.
    The command returns all the information required to establish an SSH connection.
    It also exposes a range of ports, allowing the user to connect to ports inside the container.
    
    All data in the container will be deleted when it is stopped.
    The container will remain running until it is explicitly stopped by command.
    Multiple containers can be created.
    
    - image: specify the base container image,
             leave unset to automatically select a suitable base image.
             Only Debian-based images are supported.
    
    - gpus: specify the GPU IDs to attach to the container,
            use -1 to attach all GPUs,
            leave unset to attach no GPUs.
            - exmanples:
                        gpus=-1, gpus=[0,1]
    """
    # pyrefly: ignore [missing-import]
    import docker
    
    # pyrefly: ignore [missing-import]
    import docker.errors
    
    # pyrefly: ignore [missing-import]
    import docker.models.containers
    
    # pyrefly: ignore [missing-import]
    import docker.types
    
    if len(DOCKER_CONTAINER_LIST) >= DOCKER_CONTAINER_MAX:
        return "Maximum number of containers reached"
    
    ports_len = 5
    base = "debian:13"
    
    image = image if image else base
    
    pswd = secrets.token_hex(32)
    name = f"enboite-{secrets.token_hex(16)}"
    
    with open("enboite.container.bootstrap.sh", "r", encoding="utf-8") as f:
        bootstrap = f.read()
    
    device_request_kwargs: Any = {
        "capabilities": [["gpu"]],
    }
    
    if gpus == -1:
        device_request_kwargs["count"] = -1
    elif gpus is not None and type(gpus) is list:
        device_request_kwargs["device_ids"] = [str(i) for i in gpus]
    elif gpus is None:
        pass
    else:
        raise RuntimeError("inlid argument for 'gpus'")
    
    client = None
    try:
        client = docker.from_env()
        
        # base image
        client.images.pull(base)
        
        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            if DOCKER_CONTAINER_PULL:
                client.images.pull(image)
            else:
                return "Image Not Found, pull deactivate"
        
        container = client.containers.create(
            auto_remove=True,
            image=image,
            name=name,
            command="sleep infinity",
            ports = {
                "22/tcp": None,
                **{f"{port}/tcp": None for port in range(1024, 1024+ports_len)},
            },
            device_requests=[
                docker.types.DeviceRequest(
                    **device_request_kwargs
                )
            ],
        )
        DOCKER_CONTAINER_LIST.append(container)
        
        container.start()
        
        container.reload()
        
        result = container.exec_run(
            ["bash", "-e", "-c", bootstrap],
            environment={
                "bootstrap_password_root": pswd
            },
            stream=False
        )
        
        if result.exit_code != 0:
            # pyrefly: ignore [missing-attribute]
            raise RuntimeError(f"error in the bootstrap container : code {result.exit_code}, output : {result.output.decode("utf-8", errors="replace")}")
        
        # pyrefly: ignore [unsupported-operation]
        return f"True\nusername : {"root"!r},\npassword : {pswd!r},\nip : {'localhost'!r},\nport(s) :\n  " + "\n  ".join(f"port container : {i} > host port {z[0]["HostPort"]}" for i, z in container.ports.items())
    finally:
        if client:
            client.close()

def container_images():
    """
    Return the list of Docker images that are already pulled and available locally.
    """
    # pyrefly: ignore [missing-import]
    import docker
    
    client = None
    try:
        client = docker.from_env()
        
        images = client.images.list()
        
        return "\n".join([tag for image in images for tag in image.tags])
    finally:
        if client:
            client.close()

import base64
from io import BytesIO

from PIL import Image


def screenshot(monitors_index: list[int]) -> dict[str, list[str] | str]:
    """
    Review the screenshots for all specified IDs.
    Use 'system' to retrieve the total number of screenshots.
    """
    # pyrefly: ignore [missing-import]
    import mss
    
    sct = mss.mss()
    results = []
    
    for id in monitors_index:
        id += 1
        shot = sct.grab(sct.monitors[id])
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        results.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
    return {"type": "images", "value": results}

def read_media(file: str, host: bool = False):
    """
    Allows the LLM to receive and visually analyze an image.
    The image is directly added to the conversation so that you can see and understand its content.
    Supported formats: JPG, JPEG, PNG. Other formats may work but are not guaranteed.
    """
    if not host:
        _path = _secure_path(file)
    elif FS_PERMIT_HOST:
        _path = file
    else:
        raise _client.FS.HostAccessDeniedError()
    
    if not os.path.isfile(_path):
        return 'no found the spécied input file path'
    
    with open(_path, "rb") as f:
        return {"type": "images", "value": [base64.b64encode(f.read()).decode("ascii")]}

from enboite.lib import TTS


def TTS_make_pt(input: str, ref: str = "", ref_file: str = "", x_vector_only: bool = False) -> str:
    """
    Generate a .pt voice profile file from an audio recording and return the path to the generated file.
    
    - input:
             Path to the audio file containing the voice sample.
             Minimum: 3s
             Recommended: 5–10s
             Maximum: 120s
    
    - ref:
           Text transcription of the speech contained in the audio file. This transcription is used as the reference text for voice cloning.
    - ref_file:
                Allows specifying the transcription contained in a file, which is very useful for avoiding costly memory and token operations.
    - x_vector_only:
                     Set to true when the audio cannot be transcribed. When true, the voice embedding is extracted without using a text transcription.
    
    Always prioritize `ref_file` over `ref` whenever both are available.
    
    The file path of the generated .pt voice profile.
    """
    return TTS.TTS_make_pt(input, ref, ref_file, x_vector_only)

def TTS_set_pt(file: str) -> str:
    """
    définie le .pt ( voix spécifique ) utiliser pour tout les TTS future
    """
    return TTS.TTS_fix(file)

def TTS_CHANGE() -> str:
    """
    Enable/disable text-to-speech (TTS) for LLM responses: when TTS is enabled, responses are automatically read aloud.
    """
    
    if not TTS.ready():
        return "TTS non conforme pour fonctionner"
    TTS.change()
    
    return f"status : {TTS.status()}"

def TTS_status() -> bool:
    """
    return l'état de l'activation du TTS
    """
    return TTS.ENABLE

def TTS_generator(input: str, outputPath: str) -> str:
    """
    Permet de générer un audio avec la voix définie
    
    - input:
             Texte a prononcer
    - ouput:
             WAV générer qui contient le résultat de la génération audio
             Path seulement relatif accecpeté
    
    A VRAM OOM is very likely to occur. Consider using an unload if available.
    """
    file = _secure_path(outputPath)
    
    with open(file, "wb") as f:
        f.write(TTS.TTSgen(input))
    
    return f"file in hote disk : {file}"

if TYPE_CHECKING:
    from enboite.lib import llm

SESSION_LLM: None | llm.client = None

def unload_llm() -> None:
    """
    Frees the VRAM used by the current model.
    The effect only persists until the next request that uses it.
    Prefer a tool suite if unloading is required.
    """
    if SESSION_LLM:
        SESSION_LLM.unload_llm()
    else:
        raise RuntimeError("SESSION_LLM not set:653")

def container_stop_all() -> None:
    """
    Permet de supprimer/stopper tous les container temporairer créer par vous
    """
    for container in DOCKER_CONTAINER_LIST:
        container.stop(timeout=1)


# ==== FS ==== start

def mkdir(path: str) -> str:
    """
    Creates a directory (and parent directories if needed).
    The path is relative to the shared base directory.
    Returns the absolute path of the created directory.
    """
    target = _secure_path(path, make=True)
    os.makedirs(target, exist_ok=True)
    return f"Directory created: {target}"

def file_info(path: str) -> dict:
    """
    Returns metadata about a file (size, creation time, modification time, etc.)
    The path is relative to the shared base directory.
    """
    target = _secure_path(path, make=False)
    
    if not target.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    stat = target.stat()
    return {
        "name": target.name,
        "path": str(target),
        "size_bytes": stat.st_size,
        "size_human": humanize.naturalsize(stat.st_size, binary=True),
        "st_ctime": dt.datetime.fromtimestamp(stat.st_ctime, tz=dt.UTC).isoformat(),
        "st_mtime": dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.UTC).isoformat(),
        "is_file": target.is_file(),
        "is_dir": target.is_dir()
    }

def file_write(file: str, content: str, mode: str = "w") -> str:
    """
    Writes text content to a file. Creates the file if it doesn't exist.
    For appending content, use mode='a'. The path is relative to the shared base.
    """
    target = _secure_path(file, make=True)
    with open(target, mode, encoding="utf-8") as f:
        f.write(content)
    return f"Content written to {target} ({len(content)} bytes)"

def file_delete(path: str) -> str:
    """
    Deletes a file from the shared directory.
    The path is relative to the shared base directory.
    Raises an error if the file doesn't exist or if it's a directory.
    """
    target = _secure_path(path, make=False)
    if not target.exists():
        raise FileNotFoundError("File not found")
    if target.is_dir():
        raise IsADirectoryError("Cannot delete directory with this tool")
    target.unlink()
    return f"Deleted: {target}"

def file_move(source: str, destination: str) -> str:
    """
    Moves a file from source to destination within the shared directory.
    Paths are relative to the shared base directory.
    """
    src = _secure_path(source, make=False)
    dst = _secure_path(destination, make=True)
    
    if not src.exists():
        raise FileNotFoundError("Source file not found")
    
    shutil.move(str(src), str(dst))
    return f"Moved from {source} to {destination}"

def file_copy(source: str, destination: str) -> str:
    """
    Copies a file from source to destination within the shared directory.
    Paths are relative to the shared base directory.
    """
    src = _secure_path(source, make=False)
    dst = _secure_path(destination, make=True)
    
    if not src.exists():
        raise FileNotFoundError("Source file not found:")
    
    shutil.copy2(str(src), str(dst))
    return f"Copied from {source} to {destination}"


def ls(
    path: str,
    host: bool = False
) -> str:
    """
    Lists all items contained in the specified directory.
    Takes only directories, not files.
    
    F = file
    D = directory
    """
    if not host:
        _path = _secure_path(path)
    elif FS_PERMIT_HOST:
        _path = path
    else:
        raise _client.FS.HostAccessDeniedError()
    
    results: list[str] = []
    for i in list(Path(_path).glob("*")):
        if i.is_dir():
            t = "D"
        elif i.is_file():
            t = "F"
        else:
            t = "unknown"
        
        results.append(f"{t} {i.relative_to(str(_path))}")
    
    return "\n".join(results).strip()

def cat(
    file: str,
    host: bool,
    start: int = 0,
    end: int = 2048
):
    """
    Displays the contents of the requested file.
    
    - start:
             Starting character position.
             default: 0
    
    - end:
           Ending character position (exclusive).
           This is the absolute end position, NOT the number of characters to read.
           default: 2048
    
    The maximum amount of content returned by a single call is 8192 characters.
    
    For ONLY example:
                start=0, end=8192
                start=8192, end=16384
                start=16384, end=24576
                ...
    
    Remember to use this tool multiple times if a complete read is required or if
    a single read is not sufficient.
    """
    if not host:
        _file = _secure_path(file)
    elif FS_PERMIT_HOST:
        _file = file
    else:
        raise _client.FS.HostAccessDeniedError()
    
    
    _max = 8192
    
    end = min(end, start + _max)
    
    with open(_file, "r", encoding="utf-8") as f:
        f.seek(start)
        content = f.read(end - start)
    
    return f"#Header by the tool: content: {start}-{end}: file: '{_file}'\n{content}"

def pwd(host: bool = False) -> str:
    """
    Returns the absolute path of the current directory.
    
    - host=False: returns the current workspace directory.
    - host=True: returns the current host filesystem directory.
    """
    if host:
        return os.getcwd()
    else:
        return str(BASE_SHARE)

def FS_request_host_access():
    """Requests user permission to access the host filesystem."""
    global FS_PERMIT_HOST
    if _input_live("The assistant requests access to the host filesystem.", y_n=True, color=True):
        FS_PERMIT_HOST = True
        return True
    else:
        raise _client.UserRefusedError()


# ==== FS ==== end

def execute_python(code: str, timeout: int = 60, writeoutput: bool = False) -> dict|str:
    """
    Exécute du code Python dans un sous-processus.
    
    - code:
            Code Python à exécuter.
    - timeout:
               Délai maximal d'execution secondes (défaut 60).
               max : 200
    - writeoutput:
                   Affiche le résultat de l'execution sur la console utilisateur,
                   A activer seulement si l'user requit de voir les sorties console.
    
    Returns: Dictionnaire contenant stdout, stderr, returncode.
    """
    timeout = max(0, min(200, timeout))
    if _input_live(code, "execute_python", y_n=True, color=True):
        result = {}
        
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["returncode"] = str(proc.returncode)
            if writeoutput:
                print(str(result))
        
        except subprocess.TimeoutExpired:
            result["exception"] = f"Timeout après {timeout}s"
            result["stderr"] = "Killed by timeout"
        
        except Exception as e:  # noqa: BLE001
            result["exception"] = str(e)
        
        # pyrefly: ignore [bad-return]
        return str(result)
    else:
        raise _client.UserRefusedError()

def open_folder(f: str):
    """
    Executes the command "open <f>".
    Works only with directories.
    Displays the directory on the user's screen.
    """
    folder = Path(f)
    
    if folder.expanduser().is_dir():
        subprocess.Popen(["open", str(folder)])
        return True
    else:
        raise RuntimeError("The tool expects a directory, not a file.")

def _secure_ID(ID: str) -> str:
    for i in ID:
        if not i in [str(i) for i in range(10)]:
            raise RuntimeError("invalide ID")
    return ID

def note_new(title: str, content: str) -> str:
    """
    Creates a new note.
    
    title:
    A short but descriptive title that summarizes the note's content.
    Adjust the title length to the complexity of the content so that
    it remains concise without losing important information.
    content:
    The content of the note.
    
    Returns:
    The ID of the created note.
    """
    counter_file = Path(os.path.join(BASE_NOTE, "counter.ini"))
    if not counter_file.exists():
        counter_file.write_text("0", encoding="utf-8")
    
    with open(counter_file, "r") as f:
        ID = int(_secure_ID(f.read()))
    
    with open(os.path.join(str(BASE_NOTE), f"{ID}.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"title": title, "content": content}))
    
    with open(os.path.join(str(BASE_NOTE), f"{ID}.active"), "w", encoding="utf-8") as f:
        f.write("0")
    
    with open(counter_file, "w") as f:
        f.write(str(ID+1))
    
    return str(ID)

def note_all() -> str:
    "Returns the IDs and titles of all existing notes."
    
    results: list[str] = []
    for note in Path(BASE_NOTE).glob("*.active"):
        results.append(f"ID: {note.stem}\nTitle: {json.loads(open(os.path.join(BASE_NOTE, f"{note.stem}.json"), "r", encoding="utf-8").read())["title"]}")  # noqa: SIM115
    
    return "\n".join(results).strip()

def note_read(ID: str) -> str:
    "Returns the content of a note."
    return json.loads(open(os.path.join(BASE_NOTE, f"{_secure_ID(ID)}.json"), "r", encoding="utf-8").read())["content"]

def note_rm(ID: str) -> None:
    """
    Deletes the specified note.
    
    Make sure the user has explicitly authorized this action before calling this tool.
    """
    os.unlink(os.path.join(BASE_NOTE, f"{_secure_ID(ID)}.active"))



if __name__ == "__main__":
    pass  # noqa: PIE790, RUF100
