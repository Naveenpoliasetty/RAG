
# ---------- Base image with CUDA and Python ----------
FROM nvidia/cuda:12.6.1-runtime-ubuntu22.04

# Avoid tzdata prompts
ENV DEBIAN_FRONTEND=noninteractive

# ---------- System setup ----------
RUN apt-get update && \
    apt-get install -y python3 python3-pip git && \
    rm -rf /var/lib/apt/lists/*


# ---------- Install vLLM and model deps ----------
RUN pip install --upgrade pip && \
    pip install "vllm>=0.6.0" torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121 && \
    pip install "bitsandbytes>=0.46.1"

# ---------- Copy optional startup script ----------
# (If you keep your start command separate)
# COPY start_vllm.sh /app/start_vllm.sh
# RUN chmod +x /app/start_vllm.sh

# Expose vLLM API port
EXPOSE 8000

# ---------- Check if model exists and run server ----------
CMD ["python3", "-m", "vllm.entrypoints.openai.api_server", "--model", "/models/llama3.1-8b-4bit", "--port", "8000", "--max-model-len", "4096", "--gpu-memory-utilization", "0.85", "--max-num-seqs", "2", "--max-num-batched-tokens", "8192", "--host", "0.0.0.0"]
