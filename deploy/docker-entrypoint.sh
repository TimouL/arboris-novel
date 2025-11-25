#!/bin/sh

set -e

STORAGE_DIR="${STORAGE_DIR:-/app/storage}"
PROMPTS_DIR="${PROMPTS_DIR:-/app/prompts}"
DEFAULT_PROMPTS_DIR="/app/prompts-default"

# 确保存储目录存在，处理首次启动或宿主机空目录的情况
if [ ! -d "$STORAGE_DIR" ]; then
    mkdir -p "$STORAGE_DIR"
fi

# 检查目录所有权是否为应用用户，若不是则修正以避免挂载权限问题
if [ "$(stat -c %u "$STORAGE_DIR" 2>/dev/null || echo)" != "1000" ] || \
   [ "$(stat -c %g "$STORAGE_DIR" 2>/dev/null || echo)" != "1000" ]; then
    chown -R appuser:appuser "$STORAGE_DIR" || echo "Warning: unable to adjust ownership of $STORAGE_DIR"
fi

# 如果提示词目录为空且存在默认模板，复制一份作为初始内容
if [ -d "$DEFAULT_PROMPTS_DIR" ]; then
    if [ ! -d "$PROMPTS_DIR" ]; then
        mkdir -p "$PROMPTS_DIR"
    fi
    if [ -z "$(ls -A "$PROMPTS_DIR" 2>/dev/null)" ]; then
        cp -R "$DEFAULT_PROMPTS_DIR/"* "$PROMPTS_DIR"/ 2>/dev/null || true
        chown -R appuser:appuser "$PROMPTS_DIR" || true
    fi
fi

exec "$@"
