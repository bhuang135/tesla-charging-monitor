# GitHub Deploy Guide

本機檔案路徑：

```text
C:\Users\Desktop\Git_Angela\Tesla\tesla_charging_monitor
```

GitHub repo：

```text
https://github.com/bhuang135/tesla-charging-monitor.git
```

## 1. 覆蓋本機資料夾

先把這個 zip 解壓縮，確認 `app.py` 是直接位於：

```text
C:\Users\Desktop\Git_Angela\Tesla\tesla_charging_monitor\app.py
```

不要變成：

```text
C:\Users\Desktop\Git_Angela\Tesla\tesla_charging_monitor\tesla_charging_monitor\app.py
```

## 2. 推上 GitHub 並覆蓋原本 repo

在 CMD 跑：

```bash
cd C:\Users\Desktop\Git_Angela\Tesla\tesla_charging_monitor

git init -b main
git remote set-url origin https://github.com/bhuang135/tesla-charging-monitor.git 2>NUL || git remote add origin https://github.com/bhuang135/tesla-charging-monitor.git

git add .
git commit -m "Upload multilingual Tesla charging monitor"
git push --force origin main
```

如果 `git commit` 出現：

```text
nothing to commit, working tree clean
```

直接跑：

```bash
git push --force origin main
```

## 3. Streamlit Cloud 設定

```text
Repository: bhuang135/tesla-charging-monitor
Branch: main
Main file path: app.py
```

部署後按：

```text
Manage app → Reboot app
```

## 4. 語言功能

這版已內建：

```text
繁體中文
简体中文
English
```

使用者可用畫面右下角的浮動語言球切換 `繁 / 简 / EN`，所有主要畫面會跟著切換語言。
