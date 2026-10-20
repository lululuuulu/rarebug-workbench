# 发布到 GitHub

当前交付是独立本地项目，未向任何现有私人仓库写入文件，也未创建远程公开仓库。推荐新建独立仓库 `rarebug-workbench`，避免混入历史企业材料。

## 发布前检查

在本项目根目录运行：

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_public.py
```

审阅拟提交的全部文件，特别是 `data/`、`examples/` 和许可证。`runs/`、环境文件与缓存已经被忽略。当前 examples 是特意保留的合成公开快照与评测结果。

## 创建独立仓库

如果本目录还没有 `.git`，先运行 `git init -b main`。然后配置你自己的 Git 作者信息、检查差异并提交：

```sh
git add .
git diff --cached --stat
git diff --cached
git commit -m "Add offline rare-bug reproduction workbench MVP"
```

在 GitHub 创建一个空仓库，不预先生成 README 或许可证。使用你确认的远程地址：

```sh
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

本项目不包含 GitHub token 或凭据配置。请使用你已有的 Git 身份认证。仓库名称、归属与可见性由发布者自行选择；公开前确保只提交本项目合成数据。

建议描述：`An offline, evidence-grounded workbench for synthetic rare-bug reproduction, with human approval, feedback iteration and replayable experiments.`

建议 topics：`agent`、`reproducibility`、`human-in-the-loop`、`python`、`evaluation`、`debugging`。

首次推送后检查 GitHub Actions 四个 Python 版本的任务。CI 配置存在不等于远程验证已经完成。
