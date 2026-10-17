# EnBoite
Free agents? Not anymore.

### Give your AI agent full control over a system through SSH.
![Screenshot](./media/stuck-in-jar.gif)


# Install
### for standard systems
```bash
pip install .[full]
```

### for lightweight or unconventional systems
```bash
pip install --no-cache-dir .
```


# Models

*Highly recommended model for a basic config:* `ornith-1.5:35b`

### qwen3.8:27b
- The best, perfect for effective tool usage and large autonomous loops, but requires a powerful setup.

### ornith-1.5:35b
- Close to qwen3.6:35b-a3b, but with better loop handling. Probably the most suitable for everyone.

### qwen3.6:35b-a3b
- To be avoided, handles loops poorly.

## Benchmark

| Task           | qwen3.8:27b | ornith-1.5:35b | qwen3.6:35b-a3b |
|----------------|-------|----------------|-----------------|
|***sha256***    |x%|x%|x%|

> **For those familiar with Python, you can easily run benchmarks yourself. For everyone else, I'm trying to simplify the benchmarking system.**




# Requirements
- `Ollama` ( As for other inference engines, I'm not sure whether they're compatible with the HTTP API I'm using. )
- `Native tool support`

***Hardware requirements mainly depend on the model.***
- `12+ GB VRAM`
- `32+ GB RAM`
- `15 GB+ swap`

# Python
Python 3.12.3

## Security

Security is my top priority. All sensitive actions require explicit user authorization, allowing users to maintain control over every sensitive operation.

# Available tools (table not actively maintained)
> Other tools may not be listed, as some tools are disabled by default.

| Tool | Description |
|------|-------------|
| FS_cat | Displays the contents of a file |
| FS_file_copy | Copies a file from source to destination |
| FS_file_delete | Deletes a file |
| FS_file_info | Returns file metadata (size, dates, etc.) |
| FS_file_move | Moves a file within the shared directory |
| FS_file_write | Writes/appends text to a file |
| FS_ls | Lists directory items |
| FS_mkdir | Creates a directory |
| FS_pwd | Returns the current directory |
| FS_request_host_access | Requests permission to access host filesystem |
| container_images | Lists available Docker images |
| container_start | Creates a container with SSH and exposed ports |
| container_stop_all | Stops all created containers |
| download | Downloads a resource from a URL |
| exec_python | Executes Python code |
| fetch_url_raw_v1 | Fetches a page as HTML/raw |
| fetch_url_v1 | Fetches a page as markdown |
| get_geo_ip | Geolocates an IP address |
| get_ip | Returns local and public IP |
| get_time | Returns local time and time info |
| note_all | Lists all existing notes |
| note_new | Creates a new note |
| note_read | Returns a note's content |
| note_rm | Deletes a note |
| notify | Sends a desktop notification |
| open_folder | Opens a directory on screen |
| pdf2image | Extracts images from a PDF |
| read_image | Analyzes an image (JPG/JPEG/NNG) |
| screenshot | Reviews screenshots by monitor ID |
| screenshot_file | Reviews screenshots, returns generated PNGs |
| search_web_v1 | Web search |
| search_web_v2 | Advanced web search (text, news, videos, books, images) |
| ssh_close | Closes the SSH connection |
| ssh_commande | Executes a command on an SSH session |
| ssh_login | Creates a persistent SSH connection |
| ssh_tranfer_download | Copies a file from SSH server to local |
| ssh_tranfer_upload | Copies a local file to SSH server |
| system | Provides system info (OS, hardware, etc.) |
| tool_create | Adds a reusable tool |
| unload_llm | Frees VRAM used by the current model |
| webcam_image | Captures an image from webcam |