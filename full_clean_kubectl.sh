#!/bin/bash
NAMESPACE="project1"

echo "🔍 Принудительное удаление подов..."
kubectl get pods -n $NAMESPACE -o name | xargs -r kubectl delete -n $NAMESPACE --force --grace-period=0

echo "🔧 Очистка финализаторов PVC..."
kubectl get pvc -n $NAMESPACE -o name | xargs -r kubectl patch -n $NAMESPACE -p '{"metadata":{"finalizers":[]}}' --type=merge
kubectl get pvc -n $NAMESPACE -o name | xargs -r kubectl delete -n $NAMESPACE --force --grace-period=0

echo "🔧 Очистка финализаторов namespace..."
kubectl get namespace $NAMESPACE -o json | jq '.spec.finalizers = []' | kubectl replace --raw "/api/v1/namespaces/$NAMESPACE/finalize" -f -

echo "✅ Проверка..."
kubectl get namespace $NAMESPACE 2>/dev/null || echo "Namespace $NAMESPACE удален!"