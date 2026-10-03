# 第四週：git flow, github flow 的用法

## 專案連結

1. 母專案 -- https://github.com/YI-NING-HUANG/se_example/commits/main/
   - 分支 -- https://github.com/leiuyushi0401-cpu/se_example/commits/developGitBranch
2. 子專案 (fork) -- https://github.com/leiuyushi0401-cpu/se_example/commits/main/
3. Pull Request -- https://github.com/YI-NING-HUANG/se_example/pull/1

## 這是哪種 git 流程？

本次用的是 **GitHub Flow / Forking Workflow（分叉工作流）**：

1. 母專案只保留穩定的 `main`。
2. 開發者在自己的 fork（子專案）開功能分支 `developGitBranch` 做事。
3. 做完在 fork 內 `merge` 回 fork 的 `main` 驗證，再從 fork 發 `Pull Request` 回母專案的 `main`，等母專案維護者審查合併。

## 示範紀錄

### 0. 前置：母專案已存在

母專案 `YI-NING-HUANG/se_example` 事先已有 2 個 commit：

- `1f2202a Initial commit`
- `c555fca Add .gitignore file with Python and IDE settings`

### 1. fork（在 GitHub 網頁上做）

對應題目要求的 **3. fork**。

動作：

1. 登入 `leiuyushi0401-cpu` 帳號，開啟母專案頁 https://github.com/YI-NING-HUANG/se_example
2. 按右上角 `Fork` → `Create fork` → 得到子專案 https://github.com/leiuyushi0401-cpu/se_example

驗證：子專案頁會顯示 `forked from YI-NING-HUANG/se_example`。

### 2. 建立分支

對應題目要求的 **1. 分支**。

```bash
git clone https://github.com/leiuyushi0401-cpu/se_example.git
cd se_example
git remote -v
# origin  https://github.com/leiuyushi0401-cpu/se_example.git (fetch/push)

git branch -a
git checkout -b developGitBranch
git branch
# * developGitBranch
#   main
```

### 3. 在分支上改東西、commit、push

```bash
# 在 developGitBranch 上編輯檔案（本次是改 README.md）
git status
git add -A
git commit -m "Add README explaining Git workflow"
# 產生 004c1a0 Add README explaining Git workflow

git push origin developGitBranch
# GitHub 上出現 https://github.com/leiuyushi0401-cpu/se_example/commits/developGitBranch
```

### 4. 合併

對應題目要求的 **2. 合併**。

```bash
git checkout main
git merge developGitBranch
# Fast-forward，因為 main 沒有超前，直接快轉合併，無衝突

git push origin main
# GitHub 上出現 https://github.com/leiuyushi0401-cpu/se_example/commits/main/
```

本地 `git reflog`：

```
c555fca checkout: moving from main to developGitBranch
004c1a0 commit: Add README explaining Git workflow
c555fca checkout: moving from developGitBranch to main
004c1a0 merge developGitBranch: Fast-forward
```

目前 fork 的 `main` 和 `developGitBranch` 都指向同一個 `004c1a0`，表示合併完成。

### 5. Pull Request（在 GitHub 網頁上做）

對應題目要求的 **4. pull request**。

動作：

1. 開啟母專案 PR 頁 https://github.com/YI-NING-HUANG/se_example/pulls
2. 按 `New pull request` → `compare across forks`
3. 設定 `base: YI-NING-HUANG/se_example:main` ← `head: leiuyushi0401-cpu/se_example:main`
4. 填標題 `Add README explaining Git workflow` → 按 `Create pull request`

結果：產生 https://github.com/YI-NING-HUANG/se_example/pull/1（Open 狀態），等母專案擁有者按 `Merge pull request` 才會真的寫入母專案。

## 參考資料

- Git 官方文件 -- `git-branch`：https://git-scm.com/docs/git-branch
- Git 官方文件 -- `git-merge`：https://git-scm.com/docs/git-merge
- GitHub Docs -- Fork a repo：https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo
- GitHub Docs -- Creating a pull request from a fork：https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork
- GitHub Docs -- GitHub flow：https://docs.github.com/en/get-started/using-github/github-flow
- 阮一峰 -- Git 工作流程：https://www.ruanyifeng.com/blog/2015/12/git-workflow.html
