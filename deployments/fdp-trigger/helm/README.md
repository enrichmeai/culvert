# Helm chart — fdp-trigger

fdp-trigger is **Cloud-Run-native** (see `../terraform`, the default path). This
chart is the **GKE alternative**: a minimal Deployment + Service + ServiceAccount
for running the same container on Kubernetes. It has its own templates rather
than wrapping a central chart because there is no shared runtime chart for a
plain request-driven service.

```bash
helm lint     deployments/fdp-trigger/helm
helm template fdp-trigger deployments/fdp-trigger/helm
```
