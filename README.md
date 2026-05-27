# launchs-org manifest
launchs-org を argocd でデプロイする時に使うリポジトリ

## セットアップ方法

### 1. セットアップウィザードを実行してシークレットファイルを生成する

Python 3.8 以上が必要です。

```bash
python3 setup.py
```

ウィザードに従って以下の項目を入力してください。パスワード類は Enter で自動生成されます。

| ステップ | 入力内容 |
|---|---|
| PostgreSQL 接続情報 | ホスト名・ポート・各ユーザーパスワード（自動生成可） |
| Harbor レジストリ | URL・ホスト名・builder 用ユーザー・controller 用管理者 |
| Backend | SessionSecret（自動生成可） |
| Auth — OAuth | Discord / Google / GitHub / Microsoft の Client ID・Secret・Callback URL |
| Auth — 管理者 | 管理者メール・パスワード・TOKEN_SECRET・ADMIN_SESSION_KEY（自動生成可） |
| Auth — JWT 鍵ペア | Ed25519 PEM 形式の秘密鍵・公開鍵（複数行をそのまま貼り付け） |

JWT 鍵ペアを持っていない場合は以下で生成できます。

```bash
openssl genpkey -algorithm ed25519 -out private.pem
openssl pkey -in private.pem -pubout -out public.pem
```

実行後に以下の 3 ファイルが生成されます。

```
secret.yaml
postgresql-secret.yaml
temporal-secret.yaml
```

### 2. namespace を作成する

```bash
kubectl create namespace launchs-org
kubectl apply -f namespace-buildkit.yaml
```

### 3. kustomize 管理外のリソースを手動で apply する（namespace 上書きを避けるため）

```bash
kubectl apply -f rbac-builder.yaml
```

### 4. それ以外のリソースを kustomize で apply する

```bash
kubectl apply -k .
```

## 一括実行

ウィザード実行後、以下をそのまま実行する。

```bash
kubectl create namespace launchs-org
kubectl apply -f namespace-buildkit.yaml
kubectl apply -f rbac-builder.yaml
kubectl apply -k .
```

## 削除方法

```bash
# kustomize 管理リソースを削除
kubectl delete -k .

# 手動管理リソースを削除
kubectl delete -f rbac-builder.yaml
kubectl delete -f namespace-buildkit.yaml

# namespace を削除
kubectl delete namespace launchs-org 
```

## Temporal デプロイ

Temporal は Helm チャートで管理します。kustomize とは独立して運用してください。

### 初回セットアップ

1. `python3 setup.py` を実行して `temporal-secret.yaml` を生成する（上記セットアップ手順を参照）

2. Helm リポジトリを追加する
```bash
helm repo add temporal https://go.temporal.io/helm-charts/
helm repo update
```

3. Secret を先にクラスターに適用する
```bash
kubectl apply -f temporal-secret.yaml -n launchs-org
```

4. PostgreSQL に `temporal` ユーザーと `temporaldb` / `temporalvisibilitydb` が作成されるまで待つ
```bash
kubectl get pods -n launchs-org -l application=spilo
```

5. Temporal を Helm でデプロイする（スキーマ初期化も自動実行されます）
```bash
helm install temporal temporal/temporal \
  --namespace launchs-org \
  -f temporal-values.yaml
```

### アップグレード

```bash
helm upgrade temporal temporal/temporal \
  --namespace launchs-org \
  -f temporal-values.yaml
```

### Temporal UI へのアクセス

```bash
kubectl port-forward -n launchs-org svc/temporal-web 8080:8080
# ブラウザで http://localhost:8080 を開く
```

### Temporal の削除

```bash
helm uninstall temporal --namespace launchs-org
kubectl delete -f temporal-secret.yaml -n launchs-org
```

## 注意事項

- `namespace-buildkit.yaml` と `rbac-builder.yaml` は kustomize の `namespace: launchs-org` による上書きを避けるため、kustomize からは除外しています。必ず手動で apply してください。
- `secret.yaml`、`postgresql-secret.yaml`、`temporal-secret.yaml` は `.gitignore` に含まれています。git にコミットしないよう注意してください。
