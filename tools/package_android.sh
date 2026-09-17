#!/usr/bin/env bash
# 打包脚本：把工程同步到 WSL 原生目录并构建 Android APK。
#
# 为什么需要这个脚本：
#   /mnt/d 是 NTFS 挂载盘，python-for-android / Gradle 在构建过程中需要创建符号链接、
#   修改文件权限，在这些操作上会失败。Flet 支持 Windows 宿主，因此在 Windows 侧
#   直接执行 `flet build apk` 同样可行（而且通常更快）。
#
# 注意：默认构建的是 **release** 包（flet build apk 的默认行为）。
#       只是包用 debug 密钥签名（Flet 模板行为），两者不是一回事。
#
# 用法：
#   bash tools/package_android.sh
#   ARCH=arm64-v8a BUILD_ROOT="$HOME/build" bash tools/package_android.sh
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_ROOT="${BUILD_ROOT:-$HOME/build}"
TARGET_DIR="$BUILD_ROOT/$(basename "$SOURCE_DIR")"
ARCH="${ARCH:-arm64-v8a}"

# 先归一化路径：BUILD_ROOT 里写了 .. 或多写斜杠时，
# 下面的"相等 / 包含"判断才不会失灵（`realpath -m` 不要求路径已存在）
if command -v realpath >/dev/null 2>&1; then
  TARGET_DIR="$(realpath -m "$TARGET_DIR")"
fi

# 下面的同步分支里有 `rm -rf "$TARGET_DIR"`。如果 BUILD_ROOT 被指到工程的上层
# （例如 BUILD_ROOT=/mnt/d），TARGET_DIR 就正好等于工程目录 —— 那一步会把
# **整个工程删掉**。代价太大，宁可在动手前拦下来。
if [ -z "$TARGET_DIR" ] || [ "$TARGET_DIR" = "/" ] || [ "$TARGET_DIR" = "$SOURCE_DIR" ]; then
  echo "拒绝执行：构建目录与源目录相同（$TARGET_DIR），继续下去会删掉整个工程" >&2
  echo "请把 BUILD_ROOT 指到与源目录无关的位置，例如 BUILD_ROOT=\$HOME/build" >&2
  exit 1
fi
# 两个互相包含的方向都要拦，它们的后果不同：
#   1) 构建目录在源目录里面 → rsync 会把工程拷进自己的子目录，边拷边变大（自我递归）
#   2) 源目录在构建目录里面 → `rm -rf "$TARGET_DIR"` 会连着整个工程一起删掉
case "$TARGET_DIR/" in
  "$SOURCE_DIR"/*)
    echo "拒绝执行：构建目录位于源目录内部（$TARGET_DIR 在 $SOURCE_DIR 下），同步会自我递归" >&2
    exit 1
    ;;
esac
case "$SOURCE_DIR/" in
  "$TARGET_DIR"/*)
    echo "拒绝执行：源目录位于构建目录内部（$SOURCE_DIR 在 $TARGET_DIR 下），会连工程一起删掉" >&2
    exit 1
    ;;
esac

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
