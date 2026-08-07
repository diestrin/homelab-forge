# hello-flake

Phase 1 exit-criterion sample: flake + direnv on the data disk, usable over Cursor SSH.

```bash
cd sandbox/examples/hello-flake
direnv allow
hello   # from the flake devShell
```

Aligned with [`../dev-machine`](../../../dev-machine) ideas for later L1 containers; this sample stays L0 only.
