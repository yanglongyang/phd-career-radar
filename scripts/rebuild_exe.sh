#!/usr/bin/env bash
# 重新打包 exe 且不丢用户数据（V0.2.3）
#
# 问题：PyInstaller --noconfirm 会整个删除 dist/PhD Career Radar，
# 连带清掉 exe 旁的 data/（SQLite 数据库）、.env（AI 配置）、config/（用户配置）。
# 本脚本先打包到临时目录，再把旧版 data/ .env config/ 原样复制进新包，最后替换。
#
# config/ 说明：只复制旧版已有文件（与后端 seed_user_config 的"只补缺失"一致）；
# 若新版内置默认配置有更新（如 sources.yaml 增加来源），删除 exe 旁对应文件即可重新种子化。
#
# 用法：scripts/rebuild_exe.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
APP_DIR="$DIST/PhD Career Radar"
TMP_DIST="$ROOT/build/dist_tmp"
PY="$ROOT/backend/.venv/Scripts/python.exe"

echo "==> 1/3 PyInstaller 打包（临时目录 $TMP_DIST）"
rm -rf "$TMP_DIST"
(cd "$ROOT/backend" && "$PY" -m PyInstaller launcher.spec --noconfirm --distpath "$TMP_DIST" --workpath "$ROOT/build")

echo "==> 2/3 保留旧版用户数据（data/ .env config/）"
if [ -d "$APP_DIR" ]; then
  for item in data .env config; do
    if [ -e "$APP_DIR/$item" ]; then
      cp -r "$APP_DIR/$item" "$TMP_DIST/PhD Career Radar/$item"
      echo "    保留 $item"
    fi
  done
fi

echo "==> 3/3 替换 dist"
rm -rf "$APP_DIR"
mv "$TMP_DIST/PhD Career Radar" "$APP_DIR"
rm -rf "$TMP_DIST"
echo "完成：$APP_DIR"
