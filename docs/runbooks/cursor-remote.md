# Cursor remote-dev compatibility

How Cursor SSH sessions relate to sandbox profiles on `localpower`.

## L0 (`trusted`)

- Cursor Remote SSH attaches to the **host** as user `diestrin`.
- Open folders under `/media/diestrin/data/Projects/...` (or this repo).
- Tooling comes from Home Manager + per-project flake/`direnv`.
- `forge sandbox enter <project> --profile trusted` is a convenience shell in that tree; it does not change Cursor’s attach target.

## L1 (`devcontainer`) / L4 (`agent-cell`)

- **Edit on the host, run in the container.** The project directory stays on the data disk and is bind-mounted to `/workspace` inside the container.
- Keep Cursor attached to the **host** workspace path (the real project dir). Do not require Cursor’s remote server inside the container for v1.
- Use a second terminal (or Cursor task) for:

  ```bash
  ./forge sandbox enter <project> --profile devcontainer
  # or agent-cell for stricter mounts
  ```

- **Agent workspace path:** each `agent-cell` writes
  `/media/diestrin/data/forge/agent-cells/<id>/agent-workspace.path`
  pointing at a host directory you can open remotely for cell metadata. Source edits still happen in the project bind mount.

## L2 (`incus`)

- Same edit-on-host pattern: Incus disk device mounts the project at `/workspace`.
- Enter with `./forge sandbox enter <project> --profile incus`.
- Cursor stays on the host; use `incus exec` / forge enter for the guest shell.

## Linger / systemd user services

- Host user linger (Docker rootless, host-watch timer) runs in the **host** user session.
- L1/L2/L4 sandboxes do **not** inherit host systemd user units and must not rely on `loginctl linger` inside the cell.
- Do not start a second rootless dockerd inside agent cells (no socket mounted by design).

## Practical DX

| Goal | Attach Cursor to | Run commands via |
| --- | --- | --- |
| Daily trusted coding | Host project path | Host shell / direnv |
| CI-like / language isolation | Host project path | `forge ... --profile devcontainer` |
| Untrusted agent task | Host project path (+ optional cell metadata dir) | `forge ... --profile agent-cell` |
