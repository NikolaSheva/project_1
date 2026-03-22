.PHONY: build deploy logs port-forward svc push
build:
	podman build -t quay.io/nikolasheva/project1:latest -f /home/sheva/mydata/project_1/Containerfile .

push:
	podman push quay.io/nikolasheva/project1:latest
# enter:
# 	get-quay:
# 	@echo "Logging in to Quay.io..."
# 	@podman login quay.io --username=nikolasheva
# 	@echo "Login successful"

deploy:
	kubectl apply -k k8s/base/

logs:
	kubectl logs -n project1 project1-pod -f

port-forward:
	kubectl port-forward -n project1 pod/project1-pod 10001:10000

svc:
	kubectl get svc -n project1
