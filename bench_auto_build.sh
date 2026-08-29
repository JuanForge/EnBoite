enboite \
    --model qwen3.8:27b \
    --no-save-chat \
    --limit-content-size 1800 \
    --llm-ctx 256000 \
    --thinking \
    --prompt "Automate the compilation of llama.cpp in a container. Make sure to thoroughly verify that the generated binaries are fully functional, and check whether inference works correctly on my GPU (GPU ID 0). It is highly likely that my GPU is already using all of its VRAM. In that case, adapt the verification process to check whether the GPU still works even without any available VRAM. Only speak French."
