#!/usr/bin/env bash
# 打包脚本：把工程同步到 WSL 原生目录并构建 Android APK。
#
# 为什么需要这个脚本：
#   /mnt/d 是 NTFS 挂载盘，python-for-android / Gradle 在构建过程中需要创建符号链接、
#   修改文件权限，在这些操作上会失败。Flet 支持 Windows 宿主，因此在 Windows 侧
#   直接执行 `flet build apk` 同样可行（而且通常更快）。
#
# 用法：
#   bash tools/package_android.sh            # 构建 debug APK
#   ARCH=arm64-v8a bash tools/package_android.sh
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_ROOT="${BUILD_ROOT:-$HOME/build}"
TARGET_DIR="$BUILD_ROOT/$(basename "$SOURCE_DIR")"
ARCH="${ARCH:-arm64-v8a}"

echo "源目录   : $SOURCE_DIR"
echo "构建目录 : $TARGET_DIR"
echo "架构     : $ARCH"

# ---- 1. 同步到原生文件系统 ----
mkdir -p "$TARGET_DIR"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude '.venv' \
    --exclude '.devdata' \
    --exclude '.flet' \
    --exclude 'build' \
    --exclude 'dist' \
    --exclude '__pycache__' \
    "$SOURCE_DIR/" "$TARGET_DIR/"
else
  rm -rf "$TARGET_DIR"; mkdir -p "$TARGET_DIR"
  tar -C "$SOURCE_DIR" \
    --exclude='.venv' --exclude='.devdata' --exclude='.flet' \
    --exclude='build' --exclude='dist' --exclude='__pycache__' \
    -cf - . | tar -C "$TARGET_DIR" -xf -
fi

# ---- 2. 构建 ----
cd "$TARGET_DIR"
echo "开始构建（首次会自动下载 Flutter SDK / JDK / Android SDK，耗时较长）"
flet build apk --arch "$ARCH"

# ---- 3. 把产物拷回工程目录，方便在 Windows 侧安装 ----
APK_SOURCE="$TARGET_DIR/build/apk"
if [ -d "$APK_SOURCE" ]; then
  mkdir -p "$SOURCE_DIR/dist"
  cp -f "$APK_SOURCE"/*.apk "$SOURCE_DIR/dist/" 2>/dev/null || true
  echo "产物已拷贝到: $SOURCE_DIR/dist/"
  ls -lh "$SOURCE_DIR/dist/" || true
else
  echo "未找到 $APK_SOURCE，请检查构建输出" >&2
  exit 1
fi
