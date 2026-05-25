FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ARG TARGETARCH

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        curl \
        fluxbox \
        git \
        libunrar-dev \
        p7zip-full \
        novnc \
        python3 \
        websockify \
        wget \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

# Unmodified Firefox from Mozilla — cached unless this RUN changes
RUN wget -q "https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US" -O /tmp/firefox.tar \
    && tar -xf /tmp/firefox.tar -C /opt/ \
    && rm /tmp/firefox.tar

WORKDIR /app

ENV VIRTUAL_ENV=/opt/gamma-launcher-venv
ENV PATH="/opt/firefox:/opt/gamma-launcher-venv/bin:${PATH}"

# Layer 2: Python deps + Firefox runtime libs (cached unless pyproject.toml or __init__.py changes)
COPY pyproject.toml /opt/gamma-launcher/pyproject.toml
COPY launcher/__init__.py /opt/gamma-launcher/launcher/__init__.py
RUN uv venv /opt/gamma-launcher-venv \
    && uv pip install --no-cache /opt/gamma-launcher \
    && python -m playwright install-deps firefox

# Layer 3: Launcher code (only this reruns on code changes)
COPY . /opt/gamma-launcher
RUN uv pip install --no-cache --no-deps --reinstall /opt/gamma-launcher

ENTRYPOINT ["gamma-launcher"]
CMD ["--help"]
