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

| qwen3.8:27b | ornith-1.5:35b | qwen3.6:35b-a3b |
|-------------|----------------|-----------------|
|0|0|0|

> **For those familiar with Python, you can easily run benchmarks yourself. For everyone else, I'm trying to simplify the benchmarking system.**

# Python
Python 3.12.3