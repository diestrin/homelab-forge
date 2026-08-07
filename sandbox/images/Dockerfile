# L1/L4 base image — Nix + direnv + flakes (adapted from ../dev-machine).
# Used by forge profiles: devcontainer, agent-cell.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    USER=forge \
    HOME=/home/forge \
    PATH=/home/forge/.nix-profile/bin:/nix/var/nix/profiles/default/bin:$PATH

RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends \
      bash ca-certificates curl xz-utils git sudo locales \
 && rm -rf /var/lib/apt/lists/* \
 && locale-gen en_US.UTF-8 \
 && if id -u ubuntu >/dev/null 2>&1; then \
      usermod -l forge ubuntu && groupmod -n forge ubuntu \
      && usermod -d /home/forge -m forge; \
    elif ! id -u forge >/dev/null 2>&1; then \
      useradd -m -u 1000 -s /bin/bash forge; \
    fi \
 && mkdir -m 0755 -p /nix \
 && chown forge:forge /nix

USER forge
WORKDIR /home/forge

# Single-user Nix (no daemon) — mirrors host Phase 1 posture.
RUN curl -L https://nixos.org/nix/install | sh -s -- --no-daemon \
 && mkdir -p /home/forge/.config/nix \
 && printf 'experimental-features = nix-command flakes\n' > /home/forge/.config/nix/nix.conf

# direnv + nix-direnv; hello pre-baked for smoke tests without waiting on project eval.
RUN . /home/forge/.nix-profile/etc/profile.d/nix.sh \
 && nix profile install nixpkgs#direnv nixpkgs#nix-direnv nixpkgs#hello nixpkgs#jq \
 && mkdir -p /home/forge/.config/direnv \
 && printf 'source "$HOME/.nix-profile/share/nix-direnv/direnvrc"\n' \
      > /home/forge/.config/direnv/direnvrc

USER root
RUN printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -euo pipefail' \
  '. /home/forge/.nix-profile/etc/profile.d/nix.sh' \
  'export PATH="/home/forge/.nix-profile/bin:$PATH"' \
  'eval "$(direnv hook bash)"' \
  'cd /workspace 2>/dev/null || true' \
  'if [[ -f .envrc ]]; then direnv allow . 2>/dev/null || true; fi' \
  'if [[ $# -gt 0 ]]; then exec "$@"; fi' \
  'exec bash -l' \
  > /usr/local/bin/forge-entrypoint \
 && chmod +x /usr/local/bin/forge-entrypoint \
 && printf '%s\n' \
  '. /home/forge/.nix-profile/etc/profile.d/nix.sh' \
  'export PATH="/home/forge/.nix-profile/bin:$PATH"' \
  'eval "$(direnv hook bash)"' \
  > /home/forge/.bashrc \
 && chown forge:forge /home/forge/.bashrc

# Do NOT install Docker CLI or mount docker.sock (ADR-002).
USER forge
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/forge-entrypoint"]
