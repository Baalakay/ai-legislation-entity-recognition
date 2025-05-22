# # [Choice] Python version (use -bookworm or -bullseye variants on local arm64/Apple Silicon): 3, 3.13, 3.12, 3.11, 3.10, 3.9, 3.8, 3-bookworm, 3.13-bookworm, 3.12-bookworm, 3.11-bookworm, 3.10-bookworm, 3.9-bookworm, 3.8-bookworm, 3-bullseye, 3.13-bullseye, 3.12-bullseye, 3.11-bullseye, 3.10-bullseye, 3.9-bullseye, 3.8-bullseye, 3-buster, 3.12-buster, 3.11-buster, 3.10-buster, 3.9-buster, 3.8-buster
# FROM python:3.12-bookworm
# Use the official Astral UV image with Python 3.12
# FROM ghcr.io/astral-sh/uv:python3.12-bookworm

# Uses ARM image (so no emulation and fd command will work correctly)
FROM ghcr.io/astral-sh/uv:0.7.6-python3.12-bookworm@sha256:bcd5841071395bf62952978e006f8842b6c84bc2eab20b50f172970d77939a9e

# Only set bytecode compilation, but keep default symlink behavior
ENV UV_COMPILE_BYTECODE=1
# We're explicitly NOT setting UV_LINK_MODE=copy here

# We need to set this environment variable so that uv knows where
# the virtual environment is to install packages
ENV VIRTUAL_ENV="/workspace/.venv"

# Set the working directory to match the workspaceFolder in devcontainer.json
#WORKDIR /workspace

# Make sure that the virtual environment is in the PATH so
# we can use the binaries of packages that we install such as pip
# without needing to activate the virtual environment explicitly
ENV PATH="/opt/venv/bin:$PATH"

# Remove imagemagick due to security vulnerability, then install system binaries
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    # Remove imagemagick due to https://security-tracker.debian.org/tracker/CVE-2019-10131 \
    && apt-get purge -y imagemagick imagemagick-6-common \
    # Add additional desired binaries
    && apt-get install -y --no-install-recommends ghostscript bat fd-find \
    && rm -rf /var/lib/apt/lists/* 
    