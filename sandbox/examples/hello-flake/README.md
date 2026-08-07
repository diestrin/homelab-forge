# hello-flake

Demo app for Phase 1 (L0) and Phase 2 (L0 + L1) exit criteria.

```bash
# L0 trusted (host)
./forge sandbox enter sandbox/examples/hello-flake --profile trusted
# or: cd sandbox/examples/hello-flake && direnv allow && hello

# L1 rootless Docker
./forge sandbox enter sandbox/examples/hello-flake --profile devcontainer -- hello

# L4 agent cell (project mount only)
./forge sandbox enter sandbox/examples/hello-flake --profile agent-cell -- hello
```

Image: [`../../images/Dockerfile`](../../images/Dockerfile) (adapted from [`../../../dev-machine`](../../../dev-machine)).
