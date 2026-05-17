# launchs-org manifest
launchs-org を argocd でデプロイする時に使うリポジトリ

## セットアップ方法

1. namespace を作成する
```bash
kubectl create namespace launchs-org
kubectl apply -f namespace-buildkit.yaml
```

2. `secret.yaml_template` を `secret.yaml` にコピーして適切な値を設定する
```bash
cp secret.yaml_template secret.yaml
# secret.yaml を編集する
```

3. kustomize 管理外のリソースを手動で apply する（namespace 上書きを避けるため）
```bash
kubectl apply -f namespace-buildkit.yaml
kubectl apply -f rbac-builder.yaml
```

4. それ以外のリソースを kustomize で apply する
```bash
kubectl apply -k .
```

## 一括実行

secret.yaml の準備が完了したら以下をそのまま実行する

```bash
kubectl create namespace launchs-org
kubectl apply -f namespace-buildkit.yaml
kubectl apply -f rbac-builder.yaml
kubectl apply -k .
```

## 注意事項

- `namespace-buildkit.yaml` と `rbac-builder.yaml` は kustomize の `namespace: launchs-org` による上書きを避けるため、kustomize からは除外しています。必ず手動で apply してください。
- `secret.yaml` は `.gitignore` に含まれています。
